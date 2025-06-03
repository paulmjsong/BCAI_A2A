import urllib
import arxiv
import requests
import json
import csv
import pandas as pd
from collections import Counter, defaultdict
import numpy as np # for array manipulation
import matplotlib.pyplot as plt # for data visualization
import datetime

def fetch_arxiv_papers(query, max_results = 10) -> list:
    if max_results > 10:
        max_results = 10

    search = arxiv.Search(
        query = query, # 아카이브에서 검색할 논문의 주제
        max_results = max_results, # 최대 10개 논문 검색
        sort_by = arxiv.SortCriterion.Relevance # 관련있는 논문만 검색
    )

    paper_titles = []
    for result in search.results():
        paper_titles.append({"Title": result.title, "url": result.entry_id})

    return paper_titles

if __name__ == "__main__":
    temp = fetch_arxiv_papers("RAG")

    print(temp)