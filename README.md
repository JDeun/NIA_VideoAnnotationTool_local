# Video Interaction Annotation Tool (Local Version)

이 비디오 어노테이션 도구는 [NIA_VideoAnnotationTool](https://github.com/JDeun/NIA_VideoAnnotationTool)의 웹 기반 어노테이션 툴을 로컬 환경에서 실행할 수 있도록 제작된 데스크톱 버전입니다.
사용자의 키오스크 사용 영상을 분석하고 레이블링하기 위한 도구로, 웹 버전과 동일한 기능을 제공합니다.
다만 웹과 파이썬 패키지 상의 차이로 인해 일부 기능이나 디자인에 차이가 있습니다. 현재 해당 부분은 추가 개발 중입니다.

## 주요 기능

   - 비디오 재생 및 제어 (프레임 단위 이동, 구간 지정)
   - 상호작용 유형 레이블링 (기타/접근/사용/종료)
   - 사용 인원 입력
   - 타임라인 기반 구간 관리
   - JSON 형식의 어노테이션 데이터 저장/로드

## 시스템 요구사항

   - Python 3.8 이상
   - PyQt5
   - OpenCV-Python

## 설치 방법

1. 저장소 클론
```bash
git clone https://github.com/username/NIA_VideoAnnotationTool_local.git
cd NIA_VideoAnnotationTool_local
```

2. 필요한 패키지 설치
```bash
pip install PyQt5 opencv-python pyinstaller
```

## 실행 방법

### Python 스크립트로 실행
```bash
python main.py
```

### 실행 파일 생성 및 실행

1. PyInstaller를 사용하여 실행 파일 생성
```bash
# Windows
python -m PyInstaller --onefile --windowed --name="Video Labeler" main.py

# Mac/Linux
python -m PyInstaller --onefile --windowed --name="Video_Labeler" main.py
```

2. 생성된 실행 파일 실행
- Windows: `dist/Video Labeler.exe` 실행
- Mac/Linux: `dist/Video_Labeler` 실행

## 사용 방법
### 1. 비디오 로드

   - 경로 로드: 특정 경로의 비디오 파일 로드
   - 폴더 로드: 폴더 내의 모든 비디오 파일 로드
   - 파일 로드: 개별 비디오 파일 선택 로드

### 2. 비디오 제어

   - 재생/일시정지: Space 키 또는 재생 버튼
   - 프레임 이동:
     - 이전/다음 프레임: Ctrl + ←/→
     - 이전/다음 초: ←/→
   - 구간 표시: M 키 또는 구간 표시 버튼

### 3. 구간 레이블링

   - '구간 표시' 버튼으로 시작 지점 지정
   - 원하는 종료 지점에서 다시 '구간 표시' 클릭
   - 팝업 창에서 다음 정보 입력:
     - 행동 유형 (기타/접근/사용/종료)
   - '저장' 버튼으로 구간 저장

### 4. 구간 편집

   - 타임라인의 구간을 클릭하여 정보 수정
   - 삭제 버튼으로 구간 제거

### 5. 작업 저장

   - 구간 정보는 자동 저장
   - '작성 완료' 버튼으로 최종 저장

## 데이터 형식
### 입력 데이터

   - 지원 비디오 형식: MP4, AVI, MOV, MKV
   - 권장 프레임레이트: 15fps

### 출력 데이터 (JSON)
```json
{
    "meta_data": {
        "file_name": "example.mp4",
        "format": "mp4",
        "size": 61362738,
        "width_height": [2304, 1296],
        "environment": 0,
        "frame_rate": 15,
        "total_frames": 4746,
        "camera_height": 170,
        "camera_angle": 15
    },
    "additional_info": {
        "InteractionType": "Touchscreen"
    },
    "annotations": {
        "space_context": "",
        "user_num": 1,
        "target_objects": [
            {
                "object_id": 0,
                "age": 1,
                "gender": 1,
                "disability": 2
            }
        ],
        "segmentation": [
            {
                "segment_id": 0,
                "action_type": 1,
                "start_frame": 150,
                "end_frame": 300,
                "duration": 150,
                "keyframe": 225,
                "keypoints": [
                    {
                        "object_id": 0,
                        "keypoints": []
                    }
                ]
            }
        ]
    }
}
```

## 실행 파일 배포 시 주의사항

1. 실행 파일 생성 후 반드시 다음 사항 확인:
   - 비디오 파일 로드 정상 작동
   - 구간 지정 및 저장 기능 정상 작동
   - JSON 파일 생성 정상 작동

2. 알려진 이슈
   - Windows의 경우 경로에 한글이 포함되면 실행 파일이 정상 작동하지 않을 수 있음
   - 실행 파일 위치를 이동할 경우 관련 리소스 파일도 함께 이동 필요

## 문제 해결

### 자주 발생하는 문제

1. 비디오 로드 실패
   - 지원하는 비디오 형식인지 확인
   - 파일 경로에 한글이나 특수문자 포함 여부 확인

2. 구간 저장 안됨
   - 모든 필수 필드 입력 확인
   - 로그 파일 확인

3. 타임라인 표시 오류
   - 비디오 프레임레이트 확인 (15fps 권장)
   - 프로그램 재시작 후 재시도

### 로그 확인 방법

- 프로그램 실행 디렉토리의 `video_labeler.log` 파일 확인
- 로그 레벨: INFO, ERROR 메시지 확인 가능

## 개발자 정보

- 이 도구는 NIA 프로젝트의 일환으로 개발되었습니다.
- 버그 리포트 및 기능 제안은 Issues 탭을 이용해 주세요.
- 웹 버전 링크: [NIA_VideoAnnotationTool](https://github.com/JDeun/NIA_VideoAnnotationTool)

## 라이선스
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
