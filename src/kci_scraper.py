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
# 1. 파일 경로 입력 받기 (Command Line Argument)
# ==========================================
if len(sys.argv) < 2:
    print("사용법: python3 kci_scraper.py [JSON_파일경로]")
    print("예시: python3 kci_scraper.py ./data/SSU_Datathon2025.json")
    sys.exit(1)

input_path = sys.argv[1]

if not os.path.exists(input_path):
    print(f"오류: 파일이 존재하지 않습니다. -> {input_path}")
    sys.exit(1)

print(f"📂 데이터 로드 중... ({input_path})")
with open(input_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# 전체 데이터 로드
target_nodes = data['NODE_LIST']
total_count = len(target_nodes)
updated_node_list = []

# 결과 파일명 설정 (입력 파일명 기반)
base_name = os.path.splitext(os.path.basename(input_path))[0]
temp_filename = f"{base_name}_temp.json"
output_filename = f"{base_name}_result.json"

print(f"🚀 총 {total_count:,}건의 논문에 대해 KCI 지표 수집을 시작합니다...")

# ==========================================
# 2. 헬퍼 함수 정의
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
for i, node in enumerate(tqdm(target_nodes, desc="Processing")):
    node_updated = node.copy()

    # 제목 및 저자 정보 준비
    raw_title = node.get('NODE_TTLE') or node.get('NODE_TTLE_EN', '')
    # 검색 정확도를 위해 특수문자 제거 및 공백 정리
    search_title = " ".join(re.sub(r'[^a-zA-Z0-9가-힣\s]', ' ', raw_title.strip().rstrip('.')).split())
    target_author = node.get('AUTR_NM', '')

    kci_count, fwci_val = 0, 0.0

    # 1단계: 논문 기본 정보 검색 (articleSearch)
    search_params = {'apiCode': 'articleSearch', 'key': KCI_API_KEY, 'title': search_title, 'displayCount': 5}
    try:
        resp = requests.get(BASE_URL, params=search_params, timeout=10)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            records = root.findall('.//record')

            target_record = None
            for rec in records:
                # 저자 영문명 매칭
                authors = rec.findall('.//author')
                kci_author_names = [auth.get('english', '') for auth in authors if auth.get('english')]

                if is_author_match(target_author, kci_author_names):
                    target_record = rec
                    break

            if target_record is not None:
                # 2단계: 상세 정보 조회 (articleDetail)
                art_id = target_record.find('.//articleInfo').get('article-id')
                detail_params = {'apiCode': 'articleDetail', 'key': KCI_API_KEY, 'id': art_id}
                d_resp = requests.get(BASE_URL, params=detail_params, timeout=10)

                if d_resp.status_code == 200:
                    d_root = ET.fromstring(d_resp.content)
                    d_art_info = d_root.find('.//articleInfo')

                    # 피인용 횟수 및 FWCI 추출
                    cite_elem = d_art_info.find('.//citation-count')
                    kci_count = int(cite_elem.get('kci')) if cite_elem is not None else 0

                    fwci_elem = d_art_info.find('.//fwci')
                    if fwci_elem is not None:
                        f_text = fwci_elem.get('fwci') or fwci_elem.text or '0.0'
                        fwci_val = float(f_text) if f_text.replace('.','',1).isdigit() else 0.0

        time.sleep(0.05) # 서버 부하 방지
    except Exception as e:
        # 에러 발생 시 로그만 남기고 계속 진행
        # print(f"Error processing {i}: {e}") 
        pass

    node_updated['KCI피인용'] = kci_count
    node_updated['KCI-FWCI'] = fwci_val
    updated_node_list.append(node_updated)

    # 1,000건마다 중간 저장
    if (i + 1) % 1000 == 0:
        with open(temp_filename, "w", encoding="utf-8") as f:
            json.dump({'NODE_LIST': updated_node_list}, f, ensure_ascii=False, indent=4)
        # 로그 파일에 기록을 남김
        sys.stdout.write(f"\n[알림] {i+1}건 완료 - 중간 결과 저장됨.\n")
        sys.stdout.flush()

# ==========================================
# 4. 최종 결과 저장
# ==========================================
final_json_data = {'NODE_LIST': updated_node_list}

with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(final_json_data, f, ensure_ascii=False, indent=4)

print(f"\n🎉 모든 작업 완료! 결과 파일: {output_filename}")

# 임시 파일 삭제 (선택 사항)
if os.path.exists(temp_filename):
    os.remove(temp_filename)