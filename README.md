# SSU Datathon 2025 — 사회과학 논문 토픽 지형과 인용 네트워크 파편화 분석

숭실대 데이터톤 2025 제공 데이터(DBpia 논문 메타데이터)에서 **사회과학 16개 중분류 논문 54,328건**을 골라,
무슨 주제가 연구되고 있는지(토픽)와 연구들이 서로 얼마나 연결되어 있는지(인용 네트워크)를 분석했다.
뉴스 헤드라인 키워드와 학술 토픽을 정렬해 "사회 이슈와 연구 사이의 간극"도 함께 봤다.

## 파이프라인

| 단계 | 파일 | 내용 |
|---|---|---|
| 0. 데이터 보강 | `src/kci_scraper.py`, `src/kci_scraper_law.py` | KCI Open API로 논문별 KCI ID·피인용 수·참고문헌 수 보강 (제목 정제 후 재검색) |
| 1. 필터링 | `src/final_task.py` Step 1 | 사회과학 16개 중분류만 남김 → 54,328건 |
| 2. 토픽 모델링 | `src/final_task.py` Step 2 | 제목+키워드+초록 → 다국어 SBERT 임베딩 → BERTopic (608개 → 자동 축소 417개 토픽) |
| 3. 인용 수집 | `src/final_task.py` Step 3 | KCI 피인용 상위 800편의 참고문헌을 KCI `referenceSearch` API로 병렬 수집 → 인용 관계 7,906건 |
| 4. 가교 논문 | `src/final_task.py` Step 4 | 인용 그래프(노드 7,333개)의 매개 중심성(k=300 샘플링)으로 분야를 잇는 가교 논문 순위 |
| 법학 심화 | `notebooks/01_law_keyword_topic_modeling.ipynb` | Kiwi 형태소 분석 + BERTopic + outlier reduction + KeyBERT 키워드, LLM(Gemini) 토픽 라벨링 |
| 시각화 | `notebooks/02_citation_network_news_alignment.ipynb` | 연결 요소(섬) 분포, 파편화 지도, 뉴스 키워드–토픽 정렬, 토픽 t-SNE 지형도 |

각 단계는 체크포인트 CSV를 남겨 중간에 끊겨도 이어서 실행된다.

## 결과 (`figures/`)
- `visual_island_dist.png`: 인용 네트워크는 거대 연결 요소 하나와 수십~수백 개의 작은 섬으로 갈라져 있다 (상위 20개 섬 크기 분포, log scale).
- `visual_network_map.png`, `enhanced_fragmentation_map.png`: 상위 30개 섬의 네트워크 지도.
- `final_news_topic_alignment.png`: 저출산·인공지능·고령화·디지털격차·지역소멸·청년지원 뉴스 키워드와 학술 토픽의 임베딩 유사도.
- `advanced_topic_landscape_fixed.png`: 토픽 대표 텍스트 임베딩의 t-SNE 지형도 (버블 크기 = 논문 수).

## 실행
```bash
pip install -r requirements.txt
export KCI_API_KEY=...        # KCI Open API 인증키
export GEMINI_API_KEY=...     # (선택) 토픽 라벨링
python src/kci_scraper.py data/SSU_Datathon2025.json
python src/final_task.py      # 실행 폴더의 SSU_Datathon2025_result.json 을 읽어 Step 1~4 실행
```

## 데이터
대회 제공 데이터(DBpia 논문 메타데이터 JSON, 수백 MB)와 중간 산출물은 대회 규정·용량 문제로 포함하지 않았다.
