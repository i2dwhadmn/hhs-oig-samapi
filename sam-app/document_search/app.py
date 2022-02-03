import os
import base64
import json
import random
from datetime import datetime
from urllib.parse import urlparse
# import requests
import boto3

# import pandas as pd
# import numpy as np
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
        # "body": json.dumps(results, indent=3, default=str),
        "body":results,
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


def search(search_terms):
    wrt = False
    index = 'textract' # os.environ["ES_INDEX_BASE"] + "_paragraph"
    start = datetime.now()
    
    ##################################
    service = 'es'
    ss = boto3.Session()
    credentials = ss.get_credentials()
    region = ss.region_name
    
    print("credentials", credentials.access_key, credentials.secret_key)
    
    #ES domain
    host = "vpc-dusstac-dussta-1n8niblaemqb-otcfzpck6s7czlgni6gxcb4rru.us-east-1.es.amazonaws.com"
    
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
    ES_HIGHLIGHT_FRAGMENT_SIZE = 200
    
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
    # Download and save
    # df_res = pd.DataFrame(columns=['doc_path','doc_name','score', 'highlight'])
    
    # parse results from search; returns 5 fragments from each source
    print(bool(output))
    n_results = len(output["hits"]["hits"])
    if wrt:
        print(f"The Elasticsearch query returned {n_results} results.\n")
    
    ##################################################

    if wrt:
        print("\n\nSearchResults obj:")
    # print(df_res)

    results = {}
    results["q"] = search_terms
    # results["aggregations"] = output.aggregations # will it work?
    hits = []
    # for hit in output["hits"]["hits"]:
    for i,x in enumerate(output["hits"]["hits"]):
        new_item = {}
        # new_item["_id"] = hit.get_field("_id")
        # new_item["document_path"] = os.path.split(x['_source']['name'])[0]#hit.get_field("document_name")
        new_item["document_name"] = os.path.split(x['_source']['name'])[1]#hit.get_field("document_name")
        new_item["score"] = x['_score']
        # new_item["opportunity"] = hit.get_field("opportunity")
        # new_item["agency"] = hit.get_field("agency")
        # new_item["bd_doc_type"] = hit.get_field("bd_doc_type")
        # new_item["year"] = hit.get_field("year")
        # new_item["path"] = hit.get_field("path")
        # new_item["text_type"] = hit.get_field("text_type")
        new_item["highlights"] = x['highlight']#hit.highlights[0:2]
        hits.append(new_item)
    results["hits"] = hits
    # results["total"] = search_results.total
    end = datetime.now()
    results["api_duration_seconds"] = (end - start).seconds
    results["index"] = index
    
    
    return results