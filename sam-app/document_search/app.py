import os
import base64
import json
import random
from datetime import datetime
from urllib.parse import urlparse
import boto3
import dateutil.parser as parser
import numpy as np
import re

from elasticsearch import Elasticsearch, RequestsHttpConnection
from elasticsearch.client import IndicesClient
from requests_aws4auth import AWS4Auth


def lambda_handler(event, context):
    
    print(event)
    # print(json.dumps(event, indent=3, default=str))
    search_terms = event["queryStringParameters"]["q"] # TODO 
    results = search(search_terms)
    
    # print("Results:")
    # print(json.dumps(results, indent=3, default=str))

    return {
        "headers": {"Content-Type": "application/json"},
        "statusCode": 200,
        "body": results,
        "isBase64Encoded": True,
    }
    
def create_query_json(search_terms):
    return {
        "query": {
            "bool": {
                "must": [
                    {
                        "query_string": {
                            "query": f"{search_terms}",
                            # "default_field": "text_highlight",
                            "default_operator": "and",
                        }
                    },
                ],
                # "should": [
                #     {"match": {"year": {"query": f"2020 2021", "boost": 10}}},
                #     {
                #         "match_phrase": {
                #             "text_highlight": {"query": f"{search_terms}", "boost": 100}
                #         }
                #     },
                # ],
            }
        },
        "_source": [
            "_id",
            "document_name",
            "s3_source",
            "path",
            "@timestamp",
        ],
        "highlight": {
            "number_of_fragments": 1,
            "fragment_size": 300,
            "fields": {
                "text_highlight": {
                    "pre_tags": ["<em>"],
                    "post_tags": ["</em>"],
                },
            },
        },
        # "aggregations": {
        #     "path": {"terms": {"field": "path.keyword"}},
        #     "opportunity": {"terms": {"field": "opportunity.keyword"}},
        #     "year": {"significant_terms": {"field": "year.keyword"}},
        # },
    }

def create_query(search_terms,ES_HIGHLIGHT_FRAGMENT_SIZE):
    return {
        # set up for string based queries
        "query" : {
            "query_string": {
                "query": f"{search_terms}"
            }
        },
        # set up for result fragments that are returned by ES
        "highlight" : {
            "fields" : {
                "content" : { "pre_tags" : [""], "post_tags" : [""] },
            },
            "fragment_size" : ES_HIGHLIGHT_FRAGMENT_SIZE,
            "require_field_match": False
        }
    }

def createDate(): 
    #TODO run it with a random seed everytime
    
    # regenerated only when this is run
    randconfig = {
                  'year': np.random.randint(2000,2022),
                  'month': np.random.randint(1, 12),
                  'day': np.random.randint(1,28),
                  'hour': np.random.randint(1, 24),
                  'minute': np.random.randint(1, 60),
                  'second': np.random.uniform(1, 60),
                  'sign': np.random.choice(['-','+']),
                  'tz_hr': np.random.randint(0, 12),
                  'tz_min': np.random.choice([0, 30])
                 }
                 
    pattern = '%04d%02d%02d %02d:%02d:%02.3d%s%02d%02d'
    dtstr = pattern %(randconfig['year'], randconfig['month'], randconfig['day'], randconfig['hour'], randconfig['minute'], randconfig['second'], randconfig['sign'], randconfig['tz_hr'], randconfig['tz_min'])
    
    return parser.parse(dtstr).isoformat()
    
    # pattern = '%d%02d%02d%02d%02d%02.3f%s%02d%02d' # seconds upto ms
    
    # dtstr = pattern %(randconfig['year'], randconfig['month'], randconfig['day'], randconfig['hour'], randconfig['minute'], randconfig['second'], randconfig['sign'], randconfig['tz_hr'], randconfig['tz_min'])
    
    # if return_type.lower() == 'tuple':
    #     clean = re.split('([+ -])', dtstr)
    #     gmt = datetime.strptime(clean[0], dtformat)
    #     timezone = clean[1] + clean[2]
    #     return [gmt, timezone]
    # elif return_type.lower() == 'iso':
    #     return parser.parse(dtstr).isoformat()
    # else:
    #     return dtstr
    

def get_document_url(bucket_name, object_key, expirein = 60):
    url = boto3.client('s3').generate_presigned_url(ClientMethod='get_object', 
                                            Params={'Bucket': bucket_name, 'Key': object_key},
                                            ExpiresIn=expirein)
    return url



def search(search_terms, 
            ES_HIGHLIGHT_FRAGMENT_SIZE = 200, 
            host = "vpc-dusstac-dussta-1n8niblaemqb-otcfzpck6s7czlgni6gxcb4rru.us-east-1.es.amazonaws.com" #ES domain
            ):
    wrt = False
    index = 'textract' # os.environ["ES_INDEX_BASE"] + "_paragraph"
    start = datetime.now()
    
    ##################################
    service = 'es'
    ss = boto3.Session()
    credentials = ss.get_credentials()
    region = ss.region_name
    
    if wrt:
        print("credentials", credentials.access_key, credentials.secret_key)
    
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                       region, service, session_token=credentials.token) # does this work? in NB yes... here, not sure
    
    # set up ES client for future API calls
    es = Elasticsearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    
    # size of the result fragment returned by ES
    
    # HTTP request parameters that will be sent to ES API
    searchBody = create_query(search_terms,ES_HIGHLIGHT_FRAGMENT_SIZE)
    # searchBody = create_query_json(search_terms)
    if wrt:
        print(searchBody["query"]["query_string"]["query"])

    ##################################
    
    
    # search_results = es.search(index, search_terms, query, limit=30)
    if wrt:
        print("\n\n\nsearching:")
    
    # make a query against existing index in ES via call to API
    output = es.search(index=index, size=1000, body=searchBody,
        _source = True,
        filter_path=[
            'hits.hits._id',
            'hits.hits._source',
            'hits.hits.highlight',
            'hits.hits._score'
        ],
        request_timeout=5
    )

    ##################################################
    # parse results from search; returns 5 fragments from each source
    if wrt:
        print(bool(output)) # TODO handle empty search output
        
    if not bool(output):
        n_results = 0
    else:
        n_results = len(output["hits"]["hits"])
        
    if wrt:
        print(f"The Elasticsearch query returned {n_results} results.\n")
    
    ##################################################

    if wrt:
        print("\n\nSearchResults obj:")
    # print(df_res)

    results = {}
    results["q"] = search_terms
    hits = []
    
    if bool(output):
        for i,x in enumerate(output["hits"]["hits"]):
            new_item = {}
            # new_item["document_path"] = os.path.split(x['_source']['name'])[0]#hit.get_field("document_name")
            new_item["document_name"] = os.path.split(x['_source']['name'])[1]#hit.get_field("document_name")
            new_item["score"] = x['_score']
            new_item["highlights"] = x['highlight']#hit.highlights[0:2]
            new_item["modified_date"] = createDate()
            new_item["document_url"] = get_document_url(bucket_name=x['_source']['bucket'], object_key=x['_source']['name'])
            hits.append(new_item)
        results["hits"] = hits
    else:
        results["hits"] = output
        
    # common to both
    end = datetime.now()
    results["api_duration_seconds"] = (end - start).seconds
    results["index"] = index
    
    
    return results