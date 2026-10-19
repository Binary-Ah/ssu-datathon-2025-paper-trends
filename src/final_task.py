# 파일명: final_task.py
import pandas as pd
import numpy as np
import requests
import concurrent.futures
import re
import networkx as nx
import os
import sys
from tqdm import tqdm
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from umap import UMAP
from hdbscan import HDBSCAN

# 로그 파일 설정 (노트북 닫았을 때 진행 상황 확인용)
def log_message(message):
    with open("progress.log", "a", encoding="utf-8") as f:
        f.write(message + "\n")
    print(message)

# ---------------------------------------------------------
# [Step 1] 데이터 로드 및 필터링
# ---------------------------------------------------------
if not os.path.exists("checkpoint_step1.csv"):
    log_message(">>> [Step 1] 데이터 로드 시작...")
    raw_df = pd.read_json("./SSU_Datathon2025_result.json")
    df_all = pd.json_normalize(raw_df["NODE_LIST"])
    
    target_subfields = [
        '경영학', '경제학', '관광학', '교육학', '군사학', '기타 사회과학', 
        '무역학', '문헌정보학', '법학', '사회과학 일반', '사회학', 
        '신문방송학', '인류학', '정치외교학', '지리학', '행정학'
    ]
    df = df_all[df_all['NODE_CLSS_02'].isin(target_subfields)].copy()
    df.to_csv("checkpoint_step1.csv", index=False, encoding='utf-8-sig')
    log_message(f"Step 1 완료: {len(df)}건 필터링됨.")
else:
    df = pd.read_csv("checkpoint_step1.csv")
    log_message(">>> [Step 1] 기존 데이터를 불러왔습니다.")

# ---------------------------------------------------------
# [Step 2] 토픽 모델링 (핵심 세이브 포인트)
# ---------------------------------------------------------
if not os.path.exists("checkpoint_step2_topics.csv"):
    log_message("\n>>> [Step 2] 토픽 모델링 수행 중 (BERTopic)...")
    df['full_text'] = (df['NODE_TTLE'].fillna('') + " " + 
                       df.get('KYWD', pd.Series(['']*len(df))).fillna('') + " " + 
                       df.get('ABST_KR', df.get('KR_ABST', pd.Series(['']*len(df)))).fillna(''))
    
    embedding_model = SentenceTransformer("sentence-transformers/xlm-r-100langs-bert-base-nli-stsb-mean-tokens")
    topic_model = BERTopic(embedding_model=embedding_model, nr_topics="auto", verbose=True)
    
    topics, _ = topic_model.fit_transform(df['full_text'].tolist())
    df['TOPIC_ID'] = topics
    df.to_csv("checkpoint_step2_topics.csv", index=False, encoding='utf-8-sig')
    log_message("Step 2 완료: 토픽 모델링 결과 저장됨.")
else:
    df = pd.read_csv("checkpoint_step2_topics.csv")
    log_message("\n>>> [Step 2] 기존 토픽 데이터를 불러왔습니다.")

import xml.etree.ElementTree as ET  # <--- 반드시 추가!

# ---------------------------------------------------------
# [Step 3] KCI API 인용 수집 (가이드 12p 명세 및 안정화 버전)
# ---------------------------------------------------------
if not os.path.exists("checkpoint_step3_edges.csv"):
    log_message("\n>>> [Step 3] KCI API 인용 수집 시작 (가이드 규격 최적화)...")
    KCI_API_KEY = os.environ.get("KCI_API_KEY")  # KCI Open API 인증키
    BASE_URL = "https://open.kci.go.kr/po/openapi/openApiSearch.kci"

    def get_kci_references_by_title(row):
        original_title = str(row['NODE_TTLE']).strip()
        
        # 가이드 명세에 따른 파라미터 (공백 없는 referenceSearch가 표준)
        params = {
            'apiCode': 'referenceSearch', 
            'key': KCI_API_KEY, 
            'title': original_title
        }
        
        edges = []
        try:
            # 1차 시도
            response = requests.get(BASE_URL, params=params, timeout=10)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                records = root.findall('.//record')
                
                # 결과가 없으면 제목을 다듬어 2차 시도 (특수문자 제거)
                if not records:
                    clean_title = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', original_title).strip()
                    params['title'] = clean_title
                    response = requests.get(BASE_URL, params=params, timeout=10)
                    root = ET.fromstring(response.content)
                    records = root.findall('.//record')

                for rec in records:
                    target_id = rec.get('article-id')
                    target_text = rec.text.strip() if rec.text else ""
                    if target_id or target_text:
                        edges.append({
                            'source': original_title, 
                            'target': target_id if target_id else target_text[:50]
                        })
            return edges
        except Exception as e:
            # 에러 발생 시 로그에 기록하여 원인 파악
            return []

    # 분석 대상 확대 (상위 800건)
    sample_df = df.nlargest(800, 'KCI피인용')
    sample_rows = sample_df.to_dict('records')
    all_edges = []

    # 병렬 처리 수 조정 (서버 차단 방지)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(get_kci_references_by_title, row): row for row in sample_rows}
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            res = future.result()
            if res:
                all_edges.extend(res)
            if (i + 1) % 50 == 0:
                log_message(f"진행: {i+1}/{len(sample_rows)} (현재 수집된 인용 관계: {len(all_edges)}건)")

    edge_df = pd.DataFrame(all_edges) if all_edges else pd.DataFrame(columns=['source', 'target'])
    edge_df.to_csv("checkpoint_step3_edges.csv", index=False, encoding='utf-8-sig')
    log_message(f"Step 3 종료: 총 {len(edge_df)}건의 데이터 확보.")
else:
    edge_df = pd.read_csv("checkpoint_step3_edges.csv")
# ---------------------------------------------------------
# [Step 4] 가교 분석 (데이터 유무 체크 강화)
# ---------------------------------------------------------
log_message("\n>>> [Step 4] 가교 논문 분석 시작...")
if not edge_df.empty and len(edge_df) > 0:
    G = nx.DiGraph()
    for _, row in edge_df.iterrows():
        G.add_edge(row['source'], row['target'])
    
    num_nodes = len(G.nodes())
    k_val = min(num_nodes, 300)
    log_message(f"네트워크 분석 중 (노드 {num_nodes}개, 샘플링 k={k_val})...")
    bc_scores = nx.betweenness_centrality(G, k=k_val, normalized=True)
    
    bridge_df = pd.DataFrame([{'NODE_TTLE': n, 'Betweenness': s} for n, s in bc_scores.items()])
    final_df = pd.merge(bridge_df, df, on='NODE_TTLE', how='inner')
    final_df = final_df.sort_values(by='Betweenness', ascending=False)
    final_df.to_csv("final_bridge_analysis.csv", index=False, encoding='utf-8-sig')
    log_message(">>> 모든 분석 완료! final_bridge_analysis.csv 생성됨.")
else:
    log_message("!!! 수집된 데이터가 없어 분석을 진행할 수 없습니다.")