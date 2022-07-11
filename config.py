import os

# Connect to the Google cloud Secret Manager client
#from google.cloud import secretmanager
# Connect to Google cloud storage client
#from google.cloud import storage

DEBUG = True

#flask_caching:
CACHE_TYPE = "SimpleCache"
CACHE_DEFAULT_TIMEOUT = 172800 # 2 days


DATABASE_URI = 'sqlite:////tmp/github-flask-ontospreaded.db'

#todo: get RELEASE_FILES from BSSOFoundry?
RELEASE_FILES = {"ADDICTO": "addicto-merged.owx",
                 "BCIO": "Upper%20Level%20BCIO/bcio-merged.owx", 
                 "MF": "asdfaf", 
                 "MFOEM": "asdfasdf"}

OWL_LOCATIONS = {"ADDICTO": "http://purl.obolibrary.org/obo/addicto.owl",
                 "BCIO": "http://purl.obolibrary.org/obo/bcio.owl",
                 "MF": "http://purl.obolibrary.org/obo/mf.owl",
                 "MFOEM": "http://purl.obolibrary.org/obo/mfoem.owl"}

PREFIXES = [ ["ADDICTO","http://addictovocab.org/ADDICTO_"],
             ["BFO","http://purl.obolibrary.org/obo/BFO_"],
             ["CHEBI","http://purl.obolibrary.org/obo/CHEBI_"],
             ["UBERON","http://purl.obolibrary.org/obo/UBERON_"],
             ["PATO","http://purl.obolibrary.org/obo/PATO_"],
             ["BCIO","http://humanbehaviourchange.org/ontology/BCIO_"],
             ["SEPIO","http://purl.obolibrary.org/obo/SEPIO_"],
             ["OMRSE","http://purl.obolibrary.org/obo/OMRSE_"],
             ["OBCS","http://purl.obolibrary.org/obo/OBCS_"],
             ["OGMS","http://purl.obolibrary.org/obo/OGMS_"],
             ["ENVO","http://purl.obolibrary.org/obo/ENVO_"],
             ["OBI", "http://purl.obolibrary.org/obo/OBI_"],
             ["MFOEM","http://purl.obolibrary.org/obo/MFOEM_"],
             ["MF","http://purl.obolibrary.org/obo/MF_"],
             ["CHMO","http://purl.obolibrary.org/obo/CHMO_"],
             ["DOID","http://purl.obolibrary.org/obo/DOID_"],
             ["IAO","http://purl.obolibrary.org/obo/IAO_"],
             ["ERO","http://purl.obolibrary.org/obo/ERO_"],
             ["PO","http://purl.obolibrary.org/obo/PO_"],
             ["RO","http://purl.obolibrary.org/obo/RO_"],
             ["APOLLO_SV","http://purl.obolibrary.org/obo/APOLLO_SV_"],
             ["PDRO","http://purl.obolibrary.org/obo/PDRO_"],
             ["GAZ","http://purl.obolibrary.org/obo/GAZ_"],
             ["GSSO","http://purl.obolibrary.org/obo/GSSO_"]
           ]

RDFSLABEL = "http://www.w3.org/2000/01/rdf-schema#label"

DIGIT_COUNT = 7
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')


if os.environ.get("FLASK_ENV")=='development':
    REPOSITORIES = {"AddictO": "jannahastings/addiction-ontology", "BCIO": "jannahastings/ontologies"}
else:
    REPOSITORIES = {"AddictO": "addicto-org/addiction-ontology", "BCIO": "HumanBehaviourChangeProject/ontologies"}


APP_TITLE="onto-vis"