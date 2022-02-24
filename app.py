from flask import Flask, request, g, session, redirect, url_for, render_template
from flask import render_template_string, jsonify, Response, send_file
from flask_cors import CORS
# from flask_caching import Cache
from flask_github import GitHub
import pyhornedowl
import networkx
import re
from io import StringIO  #for download
import requests #for download
import threading

import whoosh
from whoosh.qparser import MultifieldParser,QueryParser
from datetime import date

from urllib.request import urlopen

from config import *

app = Flask(__name__)
CORS(app) #cross origin across all 
app.config['CORS_HEADERS'] = 'Content-Type'
cors = CORS(app, resources={
    r"/api/*":{
        "origins":"*"
    }
})

app.config.from_object('config')
# cache = Cache(app) #caching
# set cache for each prefix in prefixes:    
# for prefix in PREFIXES: 
#     cache.set("latestID" + prefix[0], 0)
# cache.set("latestID",0) #initialise caching
# print("cache initialised")

github = GitHub(app)


class OntologyDataStore:
    node_props = {"shape":"box","style":"rounded", "font": "helvetica"}
    rel_cols = {"has part":"blue","part of":"blue","contains":"green",
                "has role":"darkgreen","is about":"darkgrey",
                "has participant":"darkblue"}

    def __init__(self):
        self.releases = {}
        self.releasedates = {}
        self.label_to_id = {}
        self.graphs = {}

    def parseRelease(self,repo):
        # Keep track of when you parsed this release
        self.graphs[repo] = networkx.MultiDiGraph()
        self.releasedates[repo] = date.today()
        #print("Release date ",self.releasedates[repo])

        # Get the ontology from the repository
        ontofilename = app.config['RELEASE_FILES'][repo]
        repositories = app.config['REPOSITORIES']
        repo_detail = repositories[repo]
        location = f"https://raw.githubusercontent.com/{repo_detail}/master/{ontofilename}"
        print("Fetching release file from", location)
        data = urlopen(location).read()  # bytes
        ontofile = data.decode('utf-8')

        # Parse it
        if ontofile:
            self.releases[repo] = pyhornedowl.open_ontology(ontofile)
            prefixes = app.config['PREFIXES']
            for prefix in prefixes:
                self.releases[repo].add_prefix_mapping(prefix[0],prefix[1])
            for classIri in self.releases[repo].get_classes():
                classId = self.releases[repo].get_id_for_iri(classIri)
                if classId:
                    classId = classId.replace(":","_")
                    # is it already in the graph?
                    if classId not in self.graphs[repo].nodes:
                        label = self.releases[repo].get_annotation(classIri, app.config['RDFSLABEL'])
                        if label:
                            self.label_to_id[label.strip()] = classId
                            # print(classId)
                            self.graphs[repo].add_node(classId,
                                                       label=label.strip().replace(" ", "\n"),
                                                **OntologyDataStore.node_props)
                        else:
                            print("Could not determine label for IRI",classIri)
                else:
                    print("Could not determine ID for IRI",classIri)
            for classIri in self.releases[repo].get_classes():
                classId = self.releases[repo].get_id_for_iri(classIri)
                if classId:
                    parents = self.releases[repo].get_superclasses(classIri)
                    for p in parents:
                        plabel = self.releases[repo].get_annotation(p, app.config['RDFSLABEL'])
                        if plabel and plabel.strip() in self.label_to_id:
                            self.graphs[repo].add_edge(self.label_to_id[plabel.strip()],
                                                       classId.replace(":", "_"), dir="back")
                    axioms = self.releases[repo].get_axioms_for_iri(classIri) # other relationships
                    for a in axioms:
                        # Example: ['SubClassOf', 'http://purl.obolibrary.org/obo/CHEBI_27732', ['ObjectSomeValuesFrom', 'http://purl.obolibrary.org/obo/RO_0000087', 'http://purl.obolibrary.org/obo/CHEBI_60809']]
                        if len(a) == 3 and a[0]=='SubClassOf' \
                            and isinstance(a[2], list) and len(a[2])==3 \
                            and a[2][0]=='ObjectSomeValuesFrom':
                            relIri = a[2][1]
                            targetIri = a[2][2]
                            rel_name = self.releases[repo].get_annotation(relIri, app.config['RDFSLABEL'])
                            targetLabel = self.releases[repo].get_annotation(targetIri, app.config['RDFSLABEL'])
                            if targetLabel and targetLabel.strip() in self.label_to_id:
                                if rel_name in OntologyDataStore.rel_cols:
                                    rcolour = OntologyDataStore.rel_cols[rel_name]
                                else:
                                    rcolour = "orange"
                                self.graphs[repo].add_edge(classId.replace(":", "_"),
                                                           self.label_to_id[targetLabel.strip()],
                                                           color=rcolour,
                                                           label=rel_name)

    def getReleaseLabels(self, repo):
        all_labels = set()
        for classIri in self.releases[repo].get_classes():
            all_labels.add(self.releases[repo].get_annotation(classIri, app.config['RDFSLABEL']))
        return( all_labels )
    
    def getReleaseIDs(self, repo):
        all_IDs = set()
        for classIri in self.releases[repo].get_classes():
            classId = self.releases[repo].get_id_for_iri(classIri)
            all_IDs.add(classId)
        return( all_IDs )

    def parseSheetData(self, repo, data):
        for entry in data:
            if 'ID' in entry and \
                    'Label' in entry and \
                    'Definition' in entry and \
                    'Parent' in entry and \
                    len(entry['ID'])>0:
                entryId = entry['ID'].replace(":", "_")
                entryLabel = entry['Label'].strip()
                self.label_to_id[entryLabel] = entryId
                self.graphs[repo].add_node(entryId, label=entryLabel.replace(" ", "\n"), **OntologyDataStore.node_props)
                if entryId in self.graphs[repo].nodes:
                    self.graphs[repo].remove_node(entryId)
                    self.graphs[repo].add_node(entryId, label=entryLabel.replace(" ", "\n"), **OntologyDataStore.node_props)
        for entry in data:
            if 'ID' in entry and \
                    'Label' in entry and \
                    'Definition' in entry and \
                    'Parent' in entry and \
                    len(entry['ID'])>0:
                entryParent = re.sub("[\[].*?[\]]", "", str(entry['Parent'])).strip()
                if entryParent in self.label_to_id:  # Subclass relations
                    # Subclass relations must be reversed for layout
                    self.graphs[repo].add_edge(self.label_to_id[entryParent],
                                               entry['ID'].replace(":", "_"), dir="back")
                for header in entry.keys():  # Other relations
                    if entry[header] and str(entry[header]).strip() and "REL" in header:
                        # Get the rel name
                        rel_names = re.findall(r"'([^']+)'", header)
                        if len(rel_names) > 0:
                            rel_name = rel_names[0]
                            if rel_name in OntologyDataStore.rel_cols:
                                rcolour = OntologyDataStore.rel_cols[rel_name]
                            else:
                                rcolour = "orange"

                            relValues = entry[header].split(";")
                            for relValue in relValues:
                                if relValue.strip() in self.label_to_id:
                                    self.graphs[repo].add_edge(entry['ID'].replace(":", "_"),
                                                               self.label_to_id[relValue.strip()],
                                                               color=rcolour,
                                                               label=rel_name)
 
 
    def getRelatedIDs(self, repo, selectedIds):
        # Add all descendents of the selected IDs, the IDs and their parents.
        # print(selectedIds)
        ids = []
        for id in selectedIds:
            try: 
                # print("got one", id)
                ids.append(id.replace(":","_"))
                if ":" in id or "_" in id: 
                    entryIri = self.releases[repo].get_iri_for_id(id.replace("_", ":"))

                    if entryIri:
                        descs = pyhornedowl.get_descendants(self.releases[repo],entryIri)
                        for d in descs:
                            ids.append(self.releases[repo].get_id_for_iri(d).replace(":","_"))
                            
                        superclasses = self.releases[repo].get_superclasses(entryIri)
                        for s in superclasses:
                            ids.append(self.releases[repo].get_id_for_iri(s).replace(":", "_"))
                if self.graphs[repo]:
                    graph_descs = None
                    try:
                        graph_descs = networkx.algorithms.dag.descendants(self.graphs[repo], id.replace(":", "_"))
                    except networkx.exception.NetworkXError:
                        print("NetworkXError relatedIDs: ", str(id))                    

                    if graph_descs is not None:
                        for g in graph_descs:
                            if g not in ids:
                                ids.append(g)
            except:
                pass
        return (ids)

    
    

    def getDotForIDs(self, repo, selectedIds):
        # Add all descendents of the selected IDs, the IDs and their parents.
        ids = OntologyDataStore.getRelatedIDs(self, repo, selectedIds) 
        subgraph = self.graphs[repo].subgraph(ids)
        P = networkx.nx_pydot.to_pydot(subgraph)
        return (P) 

    def getDotForMultipleIDs(self, repos, selectedIds):
        # Add all descendents of the selected IDs, the IDs and their parents.
        if len(repos) > 1:
            subgraphs = []
            for repo in repos: 
                ids = OntologyDataStore.getRelatedIDs(self, repo, selectedIds) #todo: do we need to differentiate?
                subgraphs.append(self.graphs[repo].subgraph(ids))
            #test combine two graphs:
            F = networkx.compose_all(subgraphs)
            # F = networkx.compose(subgraphs[0], subgraphs[1])
            P = networkx.nx_pydot.to_pydot(F)
            return (P)   
        else:              
            ids = OntologyDataStore.getRelatedIDs(self, repos[0], selectedIds) 
            subgraph = self.graphs[repos[0]].subgraph(ids)            
            P = networkx.nx_pydot.to_pydot(subgraph)
            return (P)   


    #to create a dictionary and add all info to it, in the relevant place
    def getMetaData(self, repo, allIDS):                    
        DEFN = "http://purl.obolibrary.org/obo/IAO_0000115"
        SYN = "http://purl.obolibrary.org/obo/IAO_0000118"

        label = "" 
        definition = ""
        synonyms = ""
        entries = []

        
        all_labels = set()
        for classIri in self.releases[repo].get_classes():
            classId = self.releases[repo].get_id_for_iri(classIri).replace(":", "_")
            for id in allIDS:   
                if id is not None:         
                    if classId == id:
                        label = self.releases[repo].get_annotation(classIri, app.config['RDFSLABEL']) #yes
                        iri = self.releases[repo].get_iri_for_label(label)
                        if self.releases[repo].get_annotation(classIri, DEFN) is not None:             
                            definition = self.releases[repo].get_annotation(classIri, DEFN).replace(",", "").replace("'", "").replace("\"", "")   
                        else:
                            definition = ""
                        if self.releases[repo].get_annotation(classIri, SYN) is not None:
                            synonyms = self.releases[repo].get_annotation(classIri, SYN).replace(",", "").replace("'", "").replace("\"", "") 
                        else:
                            synonyms = ""
                        entries.append({
                            "id": id,
                            "label": label, 
                            "synonyms": synonyms,
                            "definition": definition,                      
                        })
        return (entries)



ontodb = OntologyDataStore()


@app.route('/')
@app.route('/home')
def home():
    ontologies = ["BCIO", "AddictO"]
    return render_template("index.html", ontologies=ontologies)

#test func:
# @app.route('/openVisualiseAcrossSheetsVis', methods=['POST'])
# def openVisualiseAcrossSheetsVis():
#     print("openvisualise submit pressed.")
#     ontologies = ["BCIO", "AddictO"]
#     return render_template("index.html", ontologies=ontologies)

#api for onto-vis:
@app.route('/openVisualiseAcrossSheetsVis', methods=['POST'])
def openVisualiseAcrossSheetsVis():
    print("open called")
    #build data we need for dotStr query (new one!)
    if request.method == "POST":
        idString = request.form.get("idList")
        repo = request.form.get("repo")
        idList = idString.split()
        repos = repo.split()
        for repo in repos:            
            ontodb.parseRelease(repo) #todo: can we do this? 
        if len(idList) == 0:
            print("got zero length idList")
            allIds = ontodb.getReleaseIDs(repo)
            print(allIds)
            idList = []
            for ID in allIds: 
                if ID is not None and ID != "":
                    idList.append(ID.strip())
        
        # dotStr = ontodb.getDotForIDs(repo,idList).to_string()
        #test multiple repo's: 
        # repos = ["AddictO", "BCIO"]
        dotStr = ontodb.getDotForMultipleIDs(repos,idList).to_string()
        #NOTE: APP_TITLE2 can't be blank - messes up the spacing  
        APP_TITLE2 = "VISUALISATION" #could model this on calling url here? Or something else..
        #test full sheet: 
        return render_template("visualiseapi.html", sheet="selection", repo=repo, dotStr=dotStr, api=True, APP_TITLE2=APP_TITLE2)
        # return render_template("visualise.html", sheet="selection", repo=repo, dotStr=dotStr, api=True, APP_TITLE2=APP_TITLE2)
