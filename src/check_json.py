import json
import sys
import os

# ==========================================
# 설정: 기본적으로 확인할 행 번호 (입력 없으면 12000번째)
# ==========================================
DEFAULT_INDEX = 12000 

# 1. 입력 인자 처리 (파일경로, 행번호)
if len(sys.argv) < 2:
    print("사용법: python3 check_specific.py [JSON파일경로] [확인할_행번호(선택)]")
    print(f"예시: python3 check_specific.py ./data.json {DEFAULT_INDEX}")
    sys.exit(1)

file_path = sys.argv[1]

# 사용자가 행 번호를 입력했으면 그거 쓰고, 아니면 12000 사용
target_index = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_INDEX

if not os.path.exists(file_path):
    print(f"오류: 파일을 찾을 수 없습니다 -> {file_path}")
    sys.exit(1)

print(f"📂 파일 읽는 중... ({file_path})")

try:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    nodes = data.get('NODE_LIST', [])
    total_count = len(nodes)

    print(f"📊 전체 데이터 개수: {total_count:,} 건")

    # 2. 인덱스 범위 체크
    if target_index >= total_count:
        print(f"⚠️ 오류: 요청하신 {target_index}번째 데이터는 존재하지 않습니다.")
        print(f"   (현재 데이터는 0번부터 {total_count-1}번까지만 있습니다)")
        sys.exit(1)

    # 3. 데이터 출력 (target_index 위치의 데이터)
    node = nodes[target_index]
    
    print("\n" + "="*50)
    print(f"🔎 [{target_index}번째 행] 데이터 상세 정보")
    print("="*50)
    
    # 주요 정보 출력
    print(f"📌 제  목 : {node.get('NODE_TTLE') or node.get('NODE_TTLE_EN', '제목없음')}")
    print(f"👤 저  자 : {node.get('AUTR_NM', '저자없음')}")
    print(f"📅 연  도 : {node.get('PBSH', '연도없음')[:4]}")
    print(f"🏫 분  야 : {node.get('NODE_CLSS_02', '분야없음')}")
    print("-" * 50)
    
    # 수집 결과 강조
    kci_cite = node.get('KCI피인용')
    kci_fwci = node.get('KCI-FWCI')

    if kci_cite is not None:
        print(f"✅ KCI 피인용수 : {kci_cite}")
    else:
        print(f"❌ KCI 피인용수 : (수집 안 됨)")

    if kci_fwci is not None:
        print(f"✅ KCI FWCI    : {kci_fwci}")
    else:
        print(f"❌ KCI FWCI    : (수집 안 됨)")
    
    print("="*50 + "\n")

except json.JSONDecodeError:
    print("오류: JSON 파일 형식이 올바르지 않습니다. (아직 저장 중일 수 있습니다)")
except Exception as e:
    print(f"오류 발생: {e}")