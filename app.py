from cProfile import label
from flask import Flask, request, g, session, redirect, url_for, render_template
from flask import render_template_string, jsonify, Response, send_file
from flask_cors import CORS
# from flask_caching import Cache
#from flask_github import GitHub
import pyhornedowl
import networkx
import re
from io import StringIO  #for download
import requests #for download
import threading

import json

#import whoosh
#from whoosh.qparser import MultifieldParser,QueryParser
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

#get source repositories: 
query_url = f"https://api.github.com/repos/bssofoundry/bssofoundry.github.io/contents/ontology?ref=main"

query_url = f"https://api.github.com/repos/bssofoundry/bssofoundry.github.io/contents/ontology?ref=main"

headers = {'Accept': f'application/vnd.github.v3+json'}
r = requests.get(query_url, headers=headers)
linksData = r.json()
repo_names = []
# repositories = []
source_repositories = {}

for result in linksData:
    download_url = result['download_url']
    if "_outline" in download_url:
        pass
    else:
        md_html = requests.get(download_url, headers=headers).text
        # print(md_html) #full result for testing
        for line in md_html.split('\n'):             
            if "source_url: " in line: 
                source_url = line.replace("source_url: ", "").strip()
                # source_urls.append(source_url)
        for line in md_html.split('\n'):
            if "id: " in line and "- id: " not in line and "orcid" not in line:
                repo_name = line.replace("id: ", "").strip().upper() #todo: not .upper?? 
                # if repo_name != "ADDICTO":      
                repo_names.append(repo_name)
                # else: 
                #     repo_names.append("AddictO") # work-around for non-upper AddictO: todo: fix this!
        # work-around for non-upper AddictO: todo: fix this!
        if repo_name != "ADDICTO":
            source_repositories[repo_name] = source_url
        else: 
            #todo: url for AddictO not resolving - 
            source_repositories['ADDICTO'] = "https://raw.githubusercontent.com/addiction-ssa/addiction-ontology/master/addicto.owl" # source_url # todo: make this kluge exception for AddictO go away

print("source_repositories: ", source_repositories)



#location = f"https://raw.githubusercontent.com/addicto-org/addiction-ontology/master/addicto-merged.owx"
#location2 = f"https://raw.githubusercontent.com/HumanBehaviourChangeProject/ontologies/master/Upper%20Level%20BCIO/bcio-merged.owx"

#print("Fetching release file from", location)
#ontol1 = pyhornedowl.open_ontology(urlopen(location).read().decode('utf-8'))
#print("Fetching release file from", location2)
#ontol2 = pyhornedowl.open_ontology(urlopen(location2).read().decode('utf-8'))

#ontoDict = {
#    "ontologies": [
#        {
#            "label": "BCIO",
#            "name": "BCIO",
#            "ontology": ontol2
#        },
#
#        {
#            "label": "AddictO",
#             "name": "AddictO",
#            "ontology": ontol1
#        },
#    ]
#}

#github = GitHub(app)


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
        for repo in source_repositories:
            self.parseRelease(repo)
        # for repo in app.config["REPOSITORIES"]: # now getting these from BSSOFOUNDRY instead of app.config
        #     self.parseRelease(repo)

    def parseRelease(self,repo):
        # if repo != "ADDICTO": #todo: for testing BCIO, MF and MFOEM only remove this
        # print("repo is: ", repo)
        # Keep track of when you parsed this release
        self.graphs[repo] = networkx.MultiDiGraph()
        self.releasedates[repo] = date.today()
        #print("Release date ",self.releasedates[repo])
        # Get the ontology from the repository
        #todo: get ontofilename, repositories and repo_detail from BSSOFoundry
        # ontofilename = app.config['RELEASE_FILES'][repo]
        repositories = source_repositories
        # repositories = app.config['REPOSITORIES']
        repo_detail = repositories[repo]
        location = repo_detail

        print("got location", location)
        # location = f"https://raw.githubusercontent.com/{repo_detail}/master/{ontofilename}"
        # print("Fetching release file from", location)
        data = self.resolve(location) #.read()
        print("got data", data)
        data = urlopen(location).read()  # .read for bytes - needed? 
        ontofile = data.decode('utf-8')

        # Parse it
        if ontofile:
            self.releases[repo] = pyhornedowl.open_ontology(ontofile) #todo: panic error here..
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
    
    def getReleaseIDs(self, repo, excludes):
        all_IDs = set()
        for classIri in self.releases[repo].get_classes():
            classId = self.releases[repo].get_id_for_iri(classIri)
            all_IDs.add(classId)
        if len(excludes) < 1 or (len(excludes) == 1 and excludes[0] == ""): 
            all_IDs = all_IDs
        else:
            all_IDs = list(set(all_IDs) - set(excludes)) # exclude some ID's 
        return( all_IDs )

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

    def getDotForMultipleIDs(self, repos, selectedIds, excludes):
        # Add all descendents of the selected IDs, the IDs and their parents.
        if len(repos) > 1:
            subgraphs = []
            for repo in repos: 
                ids = OntologyDataStore.getRelatedIDs(self, repo, selectedIds) 
                if len(excludes) < 1 or (len(excludes) == 1 and excludes[0] == ""): 
                    ids = ids
                    # print("not excluding anything")
                else:
                    ids = list(set(ids) - set(excludes)) # exclude some ID's 
                # print("Should exclude: ", excludes)
                # print("ids after exclude: ", ids)
                subgraphs.append(self.graphs[repo].subgraph(ids))
            #test combine two graphs:
            F = networkx.compose_all(subgraphs)
            # F = networkx.compose(subgraphs[0], subgraphs[1])
            P = networkx.nx_pydot.to_pydot(F)
            return (P)   
        else:              
            ids = OntologyDataStore.getRelatedIDs(self, repos[0], selectedIds) 
            if len(excludes) < 1 or (len(excludes) == 1 and excludes[0] == ""): 
                # print("not excluding anything")
                ids = ids
            else:
                ids = list(set(ids) - set(excludes)) # exclude some ID's 
            # print("Should exclude: ", excludes)
            # print("ids after exclude: ", ids)
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
        try: 
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
        except: 
            pass
        return (entries)
        
    def resolve(self, url):
        try:
            return urlopen(url).geturl()
        except: 
            print("error resolving url: ", url)
            pass

ontodb = OntologyDataStore()

#function from onto-text-tag: 
def get_ids(ontol_list):
    # print("get_ids running here")
    checklist = []
    # for ontol in ontol_list:
    # for repo in app.config['REPOSITORIES']
    for repo in source_repositories:
        ontol = ontodb.releases[repo]
        for classIri in ontol.get_classes():
            # print("for classIri running")        
            label = ontol.get_annotation(classIri, RDFSLABEL)
            # print("label: ", label) 
            # label = ontol.get_annotation(classId, RDFSLABEL)
            if classIri:                
                classId = str(classIri).rsplit('/', 1)[1].replace('_', ':').strip()
                # print(classId)
                if classId and label:
                    # print("got classId and labels") 
                    checklist.append(classId + "|"+ label)                   
                    # print(classId, ": ", label)
                    
    return checklist

#function from onto-text-tag: 
def get_ids_for_one(current_ontol):
    # print("get_ids running here")
    checklist = []
    # for ontol in ontol_list:
    # for repo in app.config['REPOSITORIES']:
    ontol = ontodb.releases[current_ontol]
    for classIri in ontol.get_classes():
        # print("for classIri running")        
        label = ontol.get_annotation(classIri, RDFSLABEL)
        # print("label: ", label) 
        # label = ontol.get_annotation(classId, RDFSLABEL)
        if classIri:                
            classId = str(classIri).rsplit('/', 1)[1].replace('_', ':').strip()
            # print(classId)
            if classId and label:
                # print("got classId and labels") 
                checklist.append(classId + "|"+ label)                   
                # print(classId, ": ", label)
                    
    return checklist

@app.route('/')
@app.route('/home')
def home():
    ontologies_for_list = app.config["RELEASE_FILES"].keys() #todo: get these from BSSOFoundry
    # print("ontologies_for_list: ", ontologies_for_list)
    labels = get_ids(ontologies_for_list) #todo: this into [][] 
    label_list = labels
    # ontologies = ["BCIO", "AddictO"] #todo: get these from BSSOFoundry
    # ontologies = ["BCIO", "MF", "MFOEM"] #todo: get these from BSSOFoundry
    ontologies = repo_names # now from BSSOFoundry 
    # ontologies.pop(0) #todo: ADDICTO still not working, fix! This line removes it for testing
    print("ontologies are: ", ontologies)
    #label_list_two test: 
    
    label_list_two = [["a", "b", "c"], ["d", "e", "f"]] #this is fine..

    return render_template("index.html", label_list=label_list, ontologies=ontologies, label_list_two=label_list_two) 

@app.route('/get_values', methods=['POST', 'GET'])
def get_values():
    current_ontology=request.form.get("ontology") 
    # print("got request for current_ontology: ", current_ontology)

    # ontologies_for_list = app.config["RELEASE_FILES"].keys() #todo: get these from BSSOFoundry
    # print("ontologies_for_list: ", ontologies_for_list)

    labels = get_ids_for_one(current_ontology)
    # print("got labels in /get_values: ", labels)
    # print("size of labels: ", len(labels))
    label_list = labels
    # label_list = ["a", "b", "c"] #test values
    return jsonify(label_list)

@app.route('/visualise', methods=['POST'])
def visualise():
    # print("open called")
    #build data we need for dotStr query (new one!)
    if request.method == "POST":
        idString = request.form.get("idList")
        excludeIDString = request.form.get("excludeIDList")
        # print("got excludeIDString: ", excludeIDString)
        repo = request.form.get("repo")
        idListAll = idString.split(',')
        excludeIDListAll = excludeIDString.split(',')
        # print("idListAll: ", idListAll)
        idListFull = [str(word).rsplit('|')[0].strip() for word in idListAll]      
        # print("split idList is: ", idListFull)
        excludeIDList = [str(word).rsplit('|')[0].strip() for word in excludeIDListAll]  

        # print("idlistFull is: ", idListFull)
        if len(excludeIDList) < 1 or (len(excludeIDList) == 1 and excludeIDList[0] == ""): 
            idList = idListFull 
        else:
            idList = list(set(idListFull) - set(excludeIDList)) # exclude some ID's        
        # print("idList after exclude: ", idList)
        repos = repo.split()
       

        if len(idList) < 1 or (len(idList) == 1 and idList[0] == ""):
            for one_repo in repos:
                # print("got zero length idList")
                allIds = ontodb.getReleaseIDs(one_repo, excludeIDList) 
                # print(allIds)
                idList = []
                for ID in allIds: 
                    if ID is not None and ID != "":
                        idList.append(ID.strip())
        
        excludeIDListUnderscore = [s.replace(":", "_") for s in excludeIDList]
        dotStr = ontodb.getDotForMultipleIDs(repos, idList, excludeIDListUnderscore).to_string()

        #NOTE: APP_TITLE2 can't be blank - messes up the spacing  
        APP_TITLE2 = "VISUALISATION" 
        
        return render_template("visualise.html", sheet="selection", repo=repo, dotStr=dotStr, APP_TITLE2=APP_TITLE2)


if __name__ == "__main__":        # on running python app.py
    app.run(debug=app.config["DEBUG"], port=5001)        # run the flask app
