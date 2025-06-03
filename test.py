import arxiv
import requests
import pdfplumber
from io import BytesIO

def extract_text_from_pdf_url(url):
    response = requests.get(url)
    with pdfplumber.open(BytesIO(response.content)) as pdf:
        return "\n".join([page.extract_text() for page in pdf.pages])

def invoke(query, max_results = 10) -> str:
        if max_results > 10:
            max_results = 10

        search = arxiv.Search(
            query = query, # 아카이브에서 검색할 논문의 주제
            max_results = max_results, # 최대 10개 논문 검색
            sort_by = arxiv.SortCriterion.Relevance # 관련있는 논문만 검색
        )

        # 검색한 논문들의 제목과 논문의 내용 리스트에 딕셔너리 형태로 저장
        paper_list = []
        for result in search.results():
            paper_list.append({
                 "title": result.title, # 논문 제목
                 "content": extract_text_from_pdf_url(result.pdf_url) # 논문 내용
                  })

        return paper_list



if __name__ == "__main__":
     query = "RAG"

     lst = invoke(query=query, max_results=10)

     for paper in lst:
          for key, value in paper.items():
               print(f"{key}: {value}")