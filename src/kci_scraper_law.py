import json
import requests
import xml.etree.ElementTree as ET
import time
import re
import sys
import os
from tqdm.auto import tqdm

# ==========================================
# 설정 정보
# ==========================================
KCI_API_KEY = os.environ.get("KCI_API_KEY")  # KCI Open API 인증키
BASE_URL = "https://open.kci.go.kr/po/openapi/openApiSearch.kci"

# ==========================================
# 1. 파일 경로 입력 받기
# ==========================================
if len(sys.argv) < 2:
    print("사용법: python3 kci_scraper_law.py [JSON_파일경로]")
    sys.exit(1)

input_path = sys.argv[1]

print(f"📂 데이터 로드 중... ({input_path})")
with open(input_path, "r", encoding="utf-8") as f:
    data = json.load(f)

all_nodes = data['NODE_LIST']

# [중요] 법학 분야만 필터링
target_nodes = [node for node in all_nodes if node.get("NODE_CLSS_02") == "법학"]
total_count = len(target_nodes)

# 결과 파일명 설정 (원본파일명_법학_result.json)
base_name = os.path.splitext(os.path.basename(input_path))[0]
temp_filename = f"{base_name}_law_temp.json"
output_filename = f"{base_name}_law_result.json"  # 파일명이 겹치지 않게 설정

print(f"⚖️ '법학' 분야 논문 {total_count:,}건을 찾아 작업을 시작합니다...")
updated_node_list = []

# ==========================================
# 2. 헬퍼 함수
# ==========================================
def clean_and_split(text):
    if not text: return set()
    text = text.upper()
    cleaned = re.sub(r'[^A-Z0-9\s]', ' ', text)
    return set(cleaned.split())

def is_author_match(target_author, kci_authors):
    target_set = clean_and_split(target_author)
    if not target_set: return True
    for kci_auth in kci_authors:
        kci_set = clean_and_split(kci_auth)
        if len(target_set & kci_set) >= 1: return True
    return False

# ==========================================
# 3. 데이터 수집 루프
# ==========================================
for i, node in enumerate(tqdm(target_nodes, desc="Law Processing")):
    node_updated = node.copy()

    raw_title = node.get('NODE_TTLE') or node.get('NODE_TTLE_EN', '')
    search_title = " ".join(re.sub(r'[^a-zA-Z0-9가-힣\s]', ' ', raw_title.strip().rstrip('.')).split())
    target_author = node.get('AUTR_NM', '')

    kci_count, fwci_val = 0, 0.0

    search_params = {'apiCode': 'articleSearch', 'key': KCI_API_KEY, 'title': search_title, 'displayCount': 5}
    try:
        resp = requests.get(BASE_URL, params=search_params, timeout=10)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            records = root.findall('.//record')

            target_record = None
            for rec in records:
                authors = rec.findall('.//author')
                kci_author_names = [auth.get('english', '') for auth in authors if auth.get('english')]

                if is_author_match(target_author, kci_author_names):
                    target_record = rec
                    break

            if target_record is not None:
                art_id = target_record.find('.//articleInfo').get('article-id')
                detail_params = {'apiCode': 'articleDetail', 'key': KCI_API_KEY, 'id': art_id}
                d_resp = requests.get(BASE_URL, params=detail_params, timeout=10)

                if d_resp.status_code == 200:
                    d_root = ET.fromstring(d_resp.content)
                    d_art_info = d_root.find('.//articleInfo')

                    cite_elem = d_art_info.find('.//citation-count')
                    kci_count = int(cite_elem.get('kci')) if cite_elem is not None else 0

                    fwci_elem = d_art_info.find('.//fwci')
                    if fwci_elem is not None:
                        f_text = fwci_elem.get('fwci') or fwci_elem.text or '0.0'
                        fwci_val = float(f_text) if f_text.replace('.','',1).isdigit() else 0.0
        
        # [안전장치] 동시에 2개가 돌아가므로 API 부하를 줄이기 위해 대기 시간을 조금 늘림 (0.05 -> 0.1)
        time.sleep(0.1) 
    except Exception:
        pass

    node_updated['KCI피인용'] = kci_count
    node_updated['KCI-FWCI'] = fwci_val
    updated_node_list.append(node_updated)

    if (i + 1) % 100 == 0: # 법학은 개수가 적으니 100개마다 저장
        with open(temp_filename, "w", encoding="utf-8") as f:
            json.dump({'NODE_LIST': updated_node_list}, f, ensure_ascii=False, indent=4)
        sys.stdout.write(f"\n[법학] {i+1}건 완료 - 저장됨.\n")
        sys.stdout.flush()

# ==========================================
# 4. 최종 저장
# ==========================================
final_json_data = {'NODE_LIST': updated_node_list}
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(final_json_data, f, ensure_ascii=False, indent=4)

print(f"\n🎉 법학 데이터 작업 완료! 결과 파일: {output_filename}")
if os.path.exists(temp_filename): os.remove(temp_filename)