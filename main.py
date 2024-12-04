import sys
import os
from pathlib import Path
import json
import cv2
import logging
import math
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QPushButton, QFileDialog, QLabel, 
    QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QFrame, QSplitter, QStyle, QMessageBox,
    QLineEdit, QDialog, QToolTip, QButtonGroup, QRadioButton,
    QGraphicsDropShadowEffect, QSizePolicy, QShortcut,
    QGridLayout, QSlider
)
from PyQt5.QtCore import (
    Qt, QTimer, QPointF, QRectF, QSize, QPoint
)
from PyQt5.QtGui import (
    QImage, QPixmap, QPainter, QColor, QPen, QPainterPath,
    QPolygonF, QLinearGradient, QFont, QKeySequence,
    QPolygon, QBrush
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_labeler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class VideoSegment:
    def __init__(self, start_frame, end_frame, action_type=1):
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.action_type = action_type
        self.duration = end_frame - start_frame
        self.keyframe = (start_frame + end_frame) // 2  # 웹 버전과 일치
        self.keypoints = []  # 웹 버전과 일치

class TimelineWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.segments = []
        self.total_frames = 0
        self.current_frame = 0
        self.marking_start = None

        # 틴더 스타일의 색상 테마
        self.colors = {
            0: "#9e9e9e",  # 기타: 회색
            1: "#2196f3",  # 탐색: 파란색
            2: "#4caf50",  # 사용: 초록색
            3: "#fe3c72"   # 종료: 틴더 메인 색상
        }
        self.action_names = {
            0: "기타",
            1: "탐색",
            2: "사용",
            3: "종료"
        }
        
        self.setMouseTracking(True)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
            }
        """)

        # 그림자 효과 추가
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

    def set_current_frame(self, frame):
        """현재 프레임 설정"""
        self.current_frame = frame
        self.update()

    def set_total_frames(self, total):
        """전체 프레임 수 설정"""
        self.total_frames = total
        self.update()

    def set_marking_start(self, frame):
        """구간 표시 시작점 설정"""
        self.marking_start = frame
        self.update()

    def clear_marking_start(self):
        """구간 표시 시작점 초기화"""
        self.marking_start = None
        self.update()

    def mousePressEvent(self, event):
        """마우스 클릭 이벤트 처리"""
        try:
            if self.total_frames == 0 or not self.segments:
                return

            x = event.pos().x()
            width = self.width()

            # 세그먼트 선택 확인
            for i, segment in enumerate(self.segments):
                start_x = int((segment.start_frame / self.total_frames) * width)
                end_x = int((segment.end_frame / self.total_frames) * width)
                
                if start_x <= x <= end_x:
                    # 직접 부모 객체의 edit_segment 메서드 호출
                    window = self.window()
                    if hasattr(window, 'edit_segment'):
                        window.edit_segment(i)
                    return

        except Exception as e:
            logger.error(f"Error in mousePressEvent: {str(e)}", exc_info=True)

    def mouseMoveEvent(self, event):
        """마우스 이동 이벤트 처리"""
        try:
            if self.total_frames == 0 or not self.segments:
                return

            x = event.pos().x()
            width = self.width()
            
            # 타임라인 내에서 마우스 이동 시 세그먼트 정보 표시
            for segment in self.segments:
                start_x = int((segment.start_frame / self.total_frames) * width)
                end_x = int((segment.end_frame / self.total_frames) * width)
                
                if start_x <= x <= end_x:
                    fps = getattr(self.window(), 'fps', 15)
                    start_time = segment.start_frame / fps
                    end_time = segment.end_frame / fps
                    duration = segment.duration / fps
                    
                    tooltip = (f"시작: {segment.start_frame}프레임 ({start_time:.2f}초)\n"
                             f"종료: {segment.end_frame}프레임 ({end_time:.2f}초)\n"
                             f"길이: {duration:.2f}초\n"
                             f"타입: {self.action_names[segment.action_type]}")
                    QToolTip.showText(event.globalPos(), tooltip)
                    return
            
            QToolTip.hideText()
            
        except Exception as e:
            logger.error(f"Error in mouseMoveEvent: {str(e)}")

    def paintEvent(self, event):
        """타임라인 렌더링"""
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            width = self.width()
            height = self.height()

            # 배경 그리기
            painter.fillRect(0, 0, width, height, QColor("white"))

            if not self.total_frames:
                return

            # 그리드 라인 그리기 (10% 간격)
            pen = QPen(QColor("#f0f0f0"))
            pen.setWidth(1)
            painter.setPen(pen)
            for i in range(1, 10):
                x = int(width * i / 10)
                painter.drawLine(x, 0, x, height)

            # 세그먼트 그리기
            for i, segment in enumerate(self.segments):
                try:
                    start_x = int((segment.start_frame / self.total_frames) * width)
                    end_x = int((segment.end_frame / self.total_frames) * width)
                    
                    # 세그먼트 색상
                    color = QColor(self.colors.get(segment.action_type, "#9e9e9e"))
                    
                    # 그라데이션 설정
                    gradient = QLinearGradient(start_x, 0, end_x, 0)
                    gradient.setColorAt(0, color.lighter(120))
                    gradient.setColorAt(1, color)
                    
                    # 세그먼트 영역 그리기
                    path = QPainterPath()
                    rect = QRectF(start_x, height/3, end_x - start_x, height/3)
                    path.addRoundedRect(rect, 3, 3)  # 둥근 모서리
                    painter.fillPath(path, gradient)

                    # 테두리 그리기
                    painter.setPen(QPen(color.darker(110), 1))
                    painter.drawPath(path)
                    
                    # 키프레임 마커 그리기 부분 수정
                    keyframe_x = int((segment.keyframe / self.total_frames) * width)
                    marker_height = int(height/6)
                    painter.setPen(QPen(Qt.white, 2))
                    painter.drawLine(
                        keyframe_x, 
                        int(height/3 + marker_height), 
                        keyframe_x, 
                        int(2*height/3 - marker_height)
                    )
                    
                except Exception as e:
                    logger.error(f"Error drawing segment {i}: {str(e)}")

            # 구간 표시 시작점 그리기
            if self.marking_start is not None:
                try:
                    marker_x = int((self.marking_start / self.total_frames) * width)
                    pen = QPen(QColor("#ffd700"), 2)  # 굵기 2의 황금색 선
                    pen.setStyle(Qt.SolidLine)  # 실선으로 설정
                    painter.setPen(pen)
                    painter.drawLine(marker_x, 0, marker_x, height)  # 전체 높이로 그리기
                except Exception as e:
                    logger.error(f"Error drawing marking line: {str(e)}")

            # 현재 프레임 위치 표시
            if self.current_frame > 0:
                try:
                    marker_x = int((self.current_frame / self.total_frames) * width)
                    painter.setPen(QPen(QColor("#fe3c72"), 2))
                    painter.setBrush(QColor("#fe3c72"))  # 채우기 색상 설정
                    
                    # 삼각형 그리기
                    points = [
                        QPoint(marker_x, height),
                        QPoint(marker_x - 5, height - 8),
                        QPoint(marker_x + 5, height - 8)
                    ]
                    painter.drawPolygon(QPolygon(points))
                except Exception as e:
                    logger.error(f"Error drawing current frame marker: {str(e)}")

        except Exception as e:
            logger.error(f"Error in paintEvent: {str(e)}")

class SegmentDialog(QDialog):
    def __init__(self, segment, editing=False, parent=None):
        super().__init__(parent)
        self.segment = segment
        self.editing = editing
        self.delete_requested = False
        self.selected_action = segment.action_type
        self.init_ui()

    def init_ui(self):
        try:
            self.setWindowTitle('구간 정보')
            self.setMinimumWidth(400)
            layout = QVBoxLayout()
            layout.setSpacing(12)

            # 틴더 스타일 적용
            self.setStyleSheet("""
                QDialog {
                    background-color: white;
                }
                QLabel {
                    color: #424242;
                    font-size: 13px;
                }
                QSpinBox {
                    padding: 8px;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    min-height: 20px;
                }
                QPushButton {
                    padding: 10px;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    min-height: 20px;
                }
            """)

            # 프레임 입력 영역
            frames_group = QGridLayout()
            frames_group.setSpacing(10)

            # 시작 프레임
            start_label = QLabel('시작 프레임:')
            self.start_frame_input = QSpinBox()
            self.start_frame_input.setRange(0, 999999)
            self.start_frame_input.setValue(self.segment.start_frame)
            self.start_frame_input.valueChanged.connect(self.validate_frames)
            frames_group.addWidget(start_label, 0, 0)
            frames_group.addWidget(self.start_frame_input, 0, 1)

            # 종료 프레임
            end_label = QLabel('종료 프레임:')
            self.end_frame_input = QSpinBox()
            self.end_frame_input.setRange(0, 999999)
            self.end_frame_input.setValue(self.segment.end_frame)
            self.end_frame_input.valueChanged.connect(self.validate_frames)
            frames_group.addWidget(end_label, 1, 0)
            frames_group.addWidget(self.end_frame_input, 1, 1)

            # 시간 정보 표시
            fps = math.ceil(getattr(self.parent(), 'fps', 15))
            duration = (self.segment.end_frame - self.segment.start_frame) / fps
            self.duration_label = QLabel(f'길이: {duration:.2f}초')
            frames_group.addWidget(self.duration_label, 2, 0, 1, 2)

            layout.addLayout(frames_group)

            # 액션 타입 라디오 버튼
            action_group = QVBoxLayout()
            action_group.setSpacing(8)
            action_label = QLabel('액션 타입:')
            action_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            action_group.addWidget(action_label)
            
            self.action_button_group = QButtonGroup()
            
            actions = {
                0: '기타',
                1: '탐색',
                2: '사용',
                3: '종료'
            }

            for action_type, label in actions.items():
                radio = QRadioButton(label)
                radio.setStyleSheet("""
                    QRadioButton {
                        padding: 5px;
                        color: #424242;
                    }
                    QRadioButton::indicator {
                        width: 18px;
                        height: 18px;
                    }
                """)
                radio.setChecked(action_type == self.segment.action_type)
                radio.clicked.connect(lambda checked, t=action_type: self.set_action_type(t))
                self.action_button_group.addButton(radio)
                action_group.addWidget(radio)
            
            layout.addLayout(action_group)

            # 버튼 영역
            buttons = QHBoxLayout()
            buttons.setSpacing(10)
            
            # 편집 모드일 때만 삭제 버튼 표시
            if self.editing:
                delete_btn = QPushButton('삭제')
                delete_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ff4444;
                        color: white;
                    }
                    QPushButton:hover {
                        background-color: #ff6666;
                    }
                """)
                delete_btn.clicked.connect(self.request_delete)
                buttons.addWidget(delete_btn)

            save_btn = QPushButton('저장')
            save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #fe3c72;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #ff4f81;
                }
            """)
            save_btn.clicked.connect(self.accept)
            
            cancel_btn = QPushButton('취소')
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    color: #424242;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
            cancel_btn.clicked.connect(self.reject)
            
            buttons.addWidget(save_btn)
            buttons.addWidget(cancel_btn)
            
            layout.addLayout(buttons)
            self.setLayout(layout)

        except Exception as e:
            logger.error(f"Error initializing segment dialog: {str(e)}")
            QMessageBox.critical(self, '오류', f'구간 정보 대화상자 초기화 실패: {str(e)}')

    def validate_frames(self):
        """프레임 값 유효성 검사"""
        try:
            start = self.start_frame_input.value()
            end = self.end_frame_input.value()
            
            # 종료 프레임이 시작 프레임보다 작으면 조정
            if end <= start:
                self.end_frame_input.setValue(start + 1)
            
            # 길이 업데이트
            fps = math.ceil(getattr(self.parent(), 'fps', 15))
            duration = (self.end_frame_input.value() - self.start_frame_input.value()) / fps
            self.duration_label.setText(f'길이: {duration:.2f}초')
            
        except Exception as e:
            logger.error(f"Error validating frames: {str(e)}")

    def accept(self):
        """확인 버튼 클릭 시 처리"""
        try:
            if not self.delete_requested:
                self.segment.start_frame = self.start_frame_input.value()
                self.segment.end_frame = self.end_frame_input.value()
                self.segment.action_type = self.selected_action
                self.segment.duration = self.segment.end_frame - self.segment.start_frame
            super().accept()
        except Exception as e:
            logger.error(f"Error accepting dialog: {str(e)}")
            QMessageBox.critical(self, '오류', f'구간 정보 저장 실패: {str(e)}')

    def set_action_type(self, action_type):
        """액션 타입 설정"""
        try:
            self.selected_action = action_type
            self.segment.action_type = action_type
        except Exception as e:
            logger.error(f"Error setting action type: {str(e)}")

    def request_delete(self):
        """세그먼트 삭제 요청"""
        try:
            if QMessageBox.question(
                self, 
                '확인', 
                '이 구간을 삭제하시겠습니까?',
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.Yes:
                self.delete_requested = True
                self.accept()
        except Exception as e:
            logger.error(f"Error requesting segment deletion: {str(e)}")

class VideoLabeler(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('비디오 라벨링 도구')
        # 전체 창 크기를 화면의 80%로 설정
        screen = QApplication.primaryScreen().size()
        self.resize(int(screen.width() * 0.8), int(screen.height() * 0.8))
        
        # 메인 위젯이 키보드 포커스를 가지도록 설정
        self.setFocusPolicy(Qt.StrongFocus)
        
        # 틴더 스타일 전역 설정
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f6f7f8;
            }
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QPushButton {
                font-weight: 500;
            }
            QLabel {
                color: #424242;
            }
        """)
        
        # 변수 초기화
        self.current_files = []
        self.current_file_index = -1
        self.cap = None
        self.fps = 15
        self.current_frame = 0
        self.total_frames = 0
        self.is_playing = False
        self.segments = []
        self.marking_segment = False
        self.current_segment = None
        self.timeline = None
        self.has_unsaved_changes = False

        # 타이머 초기화
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        
        # 메인 위젯과 레이아웃 설정
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        layout = QHBoxLayout()
        layout.setSpacing(16)  # 섹션 간 간격
        layout.setContentsMargins(16, 16, 16, 16)  # 전체 여백

        # 좌우 섹션 초기화
        left_section = self.init_left_section()
        right_section = self.init_right_section()
        
        # 섹션 너비 비율 설정
        layout.addLayout(left_section, stretch=75)  # 75%
        layout.addLayout(right_section, stretch=25)  # 25%
        
        main_widget.setLayout(layout)
        
        # 초기 버튼 상태 설정
        self.enable_video_controls(False)

        # 키보드 단축키 설정
        QShortcut(QKeySequence.Save, self, self.save_annotations)
        QShortcut(QKeySequence(Qt.Key_Space), self, self.toggle_play)
        QShortcut(QKeySequence(Qt.Key_M), self, self.mark_segment)
        self.play_shortcut = Qt.Key_Space
        self.prev_sec_shortcut = Qt.Key_Left
        self.next_sec_shortcut = Qt.Key_Right
        self.prev_frame_shortcut = Qt.Key_Left | Qt.ControlModifier
        self.next_frame_shortcut = Qt.Key_Right | Qt.ControlModifier
        self.mark_shortcut = Qt.Key_M

        # UI 초기화
        self.init_ui()

    def setup_shortcuts(self):
        """키보드 단축키 설정"""
        try:
            # 스페이스바: 재생/일시정지
            self.play_shortcut = Qt.Key_Space
            
            # 좌우 화살표: 1초 이동
            self.prev_sec_shortcut = Qt.Key_Left
            self.next_sec_shortcut = Qt.Key_Right
            
            # Ctrl + 좌우 화살표: 1프레임 이동
            self.prev_frame_shortcut = Qt.Key_Left | Qt.ControlModifier
            self.next_frame_shortcut = Qt.Key_Right | Qt.ControlModifier
            
            # M: 구간 표시
            self.mark_shortcut = Qt.Key_M
            
        except Exception as e:
            logger.error(f"Error setting up shortcuts: {str(e)}")

    def init_ui(self):
        """UI 초기화"""
        try:
            # 메인 위젯
            main_widget = QWidget()
            self.setCentralWidget(main_widget)
            layout = QHBoxLayout()

            # 왼쪽 섹션 초기화
            left_section = self.init_left_section()
            
            # 오른쪽 섹션 초기화
            right_section = self.init_right_section()
            
            # 레이아웃 설정
            layout.addLayout(left_section, stretch=7)  # 70% 너비
            layout.addLayout(right_section, stretch=3)  # 30% 너비
            
            main_widget.setLayout(layout)
            
            # 초기 버튼 상태 설정
            self.enable_video_controls(False)
            
        except Exception as e:
            logger.error(f"Error initializing UI: {str(e)}")
            QMessageBox.critical(self, '오류', f'UI 초기화 실패: {str(e)}')

    def init_left_section(self):
        """왼쪽 섹션 UI 초기화"""
        try:
            left_section = QVBoxLayout()
            left_section.setSpacing(8)  # 요소들 간의 간격 설정
            left_section.setContentsMargins(8, 8, 8, 8)  # 전체 여백 설정
            
            # 비디오 컨테이너 생성 및 설정
            video_container = QWidget()
            video_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 가능한 크게 확장
            video_container.setStyleSheet("""
                QWidget {
                    background-color: black;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }
            """)
            
            # 비디오 레이블 설정
            self.video_label = QLabel(video_container)
            self.video_label.setAlignment(Qt.AlignCenter)
            self.video_label.setStyleSheet("border: none;")  # 레이블 자체의 테두리 제거
            
            # 비디오 레이블을 컨테이너의 중앙에 위치시키는 레이아웃
            video_layout = QVBoxLayout(video_container)
            video_layout.setContentsMargins(0, 0, 0, 0)  # 여백 제거
            video_layout.addWidget(self.video_label)
            
            left_section.addWidget(video_container, stretch=1)  # stretch=1로 설정하여 최대한의 공간 사용
            
            # 컨트롤 섹션 초기화
            controls_layout = self.init_controls()
            left_section.addLayout(controls_layout)
            
            # 타임라인 초기화
            self.timeline = TimelineWidget(parent=self)
            left_section.addWidget(self.timeline)
            
            return left_section
                
        except Exception as e:
            logger.error(f"Error initializing left section: {str(e)}")
            raise

    def init_controls(self):
        """컨트롤 섹션 UI 초기화"""
        try:
            controls = QVBoxLayout()
            controls.setSpacing(8)  # 버튼 간격 설정

            # 비디오 슬라이더 추가
            self.video_slider = QSlider(Qt.Horizontal)
            self.video_slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    border: 1px solid #ddd;
                    height: 8px;
                    background: #ffffff;
                    margin: 2px 0;
                    border-radius: 4px;
                }
                QSlider::handle:horizontal {
                    background: #fe3c72;
                    border: 1px solid #ddd;
                    width: 18px;
                    margin: -5px 0;
                    border-radius: 9px;
                }
                QSlider::handle:horizontal:hover {
                    background: #f28cb1;
                }
            """)
            self.video_slider.setFocusPolicy(Qt.ClickFocus)  # 키보드 포커스 정책 설정
            self.video_slider.sliderMoved.connect(self.slider_moved)
            self.video_slider.sliderPressed.connect(self.slider_pressed)
            self.video_slider.sliderReleased.connect(self.slider_released)
            controls.addWidget(self.video_slider)
            
            # 기존 컨트롤 버튼들을 담을 수평 레이아웃
            buttons_layout = QHBoxLayout()
            
            # 틴더 스타일 버튼 기본 스타일
            button_style = """
                QPushButton {
                    background-color: white;
                    color: #424242;
                    padding: 8px 15px;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    min-height: 20px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #f0f0f0;
                }
                QPushButton:disabled {
                    background-color: #f5f5f5;
                    color: #999;
                }
            """
            
            # 이전 프레임
            self.prev_frame_btn = QPushButton('◀◀ 이전 프레임')
            self.prev_frame_btn.setStyleSheet(button_style)
            self.prev_frame_btn.clicked.connect(lambda: self.move_frame(-1))
            buttons_layout.addWidget(self.prev_frame_btn)
            
            # 이전 초
            self.prev_sec_btn = QPushButton('◀ 이전 초')
            self.prev_sec_btn.setStyleSheet(button_style)
            self.prev_sec_btn.clicked.connect(lambda: self.move_second(-1))
            buttons_layout.addWidget(self.prev_sec_btn)
            
            # 재생/일시정지
            self.play_btn = QPushButton('재생')
            self.play_btn.setStyleSheet(button_style.replace('background-color: white', 'background-color: #fe3c72') \
                                .replace('color: #424242', 'color: white') + """
                QPushButton:hover {
                    background-color: #f28cb1;
                    color: white;
                }
            """)
            self.play_btn.clicked.connect(self.toggle_play)
            buttons_layout.addWidget(self.play_btn)
            
            # 다음 초
            self.next_sec_btn = QPushButton('다음 초 ▶')
            self.next_sec_btn.setStyleSheet(button_style)
            self.next_sec_btn.clicked.connect(lambda: self.move_second(1))
            buttons_layout.addWidget(self.next_sec_btn)
            
            # 다음 프레임
            self.next_frame_btn = QPushButton('다음 프레임 ▶▶')
            self.next_frame_btn.setStyleSheet(button_style)
            self.next_frame_btn.clicked.connect(lambda: self.move_frame(1))
            buttons_layout.addWidget(self.next_frame_btn)
            
            # 구간 표시
            self.mark_btn = QPushButton('구간 표시')
            mark_button_style = button_style.replace('background-color: white', 'background-color: #fe3c72') \
                                .replace('color: #424242', 'color: white') + """
                QPushButton:hover {
                    background-color: #f28cb1;
                    color: white;
                }
            """
            self.mark_btn.setStyleSheet(mark_button_style)
            self.mark_btn.clicked.connect(self.mark_segment)
            buttons_layout.addWidget(self.mark_btn)
            
            # 사용자 수
            user_num_container = QWidget()
            user_num_container.setStyleSheet("""
                QWidget {
                    background-color: white;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    min-height: 20px;
                }
            """)
            user_num_layout = QHBoxLayout(user_num_container)
            user_num_layout.setContentsMargins(10, 0, 10, 0)
            
            user_num_label = QLabel('사용 인원:')
            user_num_label.setStyleSheet("border: none; color: #424242;")
            self.user_num_spin = QSpinBox()
            self.user_num_spin.setRange(1, 10)
            self.user_num_spin.setValue(1)
            self.user_num_spin.setStyleSheet("""
                QSpinBox {
                    border: none;
                    background: transparent;
                    min-width: 50px;
                }
            """)
            self.user_num_spin.setFocusPolicy(Qt.ClickFocus)  # 키보드 포커스 정책 설정
            user_num_layout.addWidget(user_num_label)
            user_num_layout.addWidget(self.user_num_spin)
            buttons_layout.addWidget(user_num_container)
            
            # 시간 표시
            self.time_label = QLabel('프레임: 0/0 | 시간: 0.00s')
            self.time_label.setStyleSheet("""
                QLabel {
                    background-color: white;
                    color: #424242;
                    padding: 0 15px;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    min-height: 20px;
                    min-width: 250px;
                    qproperty-alignment: AlignCenter;
                }
            """)
            buttons_layout.addWidget(self.time_label)
            
            # buttons_layout을 controls에 추가
            controls.addLayout(buttons_layout)
            
            return controls
                
        except Exception as e:
            logger.error(f"Error initializing controls: {str(e)}")
            raise

    def init_right_section(self):
        """오른쪽 섹션 UI 초기화"""
        try:
            right_section = QVBoxLayout()
            
            # 파일 입력 영역
            file_input = QVBoxLayout()
            
            # 경로 로드
            path_layout = QHBoxLayout()
            self.path_input = QLineEdit()
            self.path_input.setPlaceholderText("비디오 파일 경로 입력")
            self.path_input.setStyleSheet("""
                QLineEdit {
                    padding: 5px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }
            """)
            
            self.load_path_btn = QPushButton('경로 로드')
            self.load_path_btn.setStyleSheet("""
                QPushButton {
                    padding: 5px 10px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background-color: white;
                }
                QPushButton:hover {
                    background-color: #f0f0f0;
                }
            """)
            self.load_path_btn.clicked.connect(self.load_path)
            
            path_layout.addWidget(self.path_input)
            path_layout.addWidget(self.load_path_btn)
            file_input.addLayout(path_layout)
            
            # 폴더/파일 로드 버튼
            btn_layout = QHBoxLayout()
            self.load_dir_btn = QPushButton('폴더 로드')
            self.load_file_btn = QPushButton('파일 로드')
            
            for btn in [self.load_dir_btn, self.load_file_btn]:
                btn.setStyleSheet("""
                    QPushButton {
                        padding: 5px 10px;
                        border: 1px solid #ddd;
                        border-radius: 4px;
                        background-color: white;
                    }
                    QPushButton:hover {
                        background-color: #f0f0f0;
                    }
                """)
            
            self.load_dir_btn.clicked.connect(self.load_directory)
            self.load_file_btn.clicked.connect(self.load_files)
            
            btn_layout.addWidget(self.load_dir_btn)
            btn_layout.addWidget(self.load_file_btn)
            file_input.addLayout(btn_layout)
            
            # 프로그레스바
            self.progress_bar = QProgressBar()
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #4CAF50;
                }
            """)
            self.progress_bar.hide()
            file_input.addWidget(self.progress_bar)
            
            right_section.addLayout(file_input)
            
            # 파일 목록
            list_container = QVBoxLayout()
            list_label = QLabel("파일 목록")
            list_label.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    padding: 5px;
                }
            """)
            list_container.addWidget(list_label)
            
            self.file_list = QTableWidget()
            self.file_list.setColumnCount(3)
            self.file_list.setHorizontalHeaderLabels(['파일명', '상태', '동작'])
            header = self.file_list.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            
            self.file_list.setStyleSheet("""
                QTableWidget {
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background-color: white;
                }
                QTableWidget::item {
                    padding: 5px;
                }
                QHeaderView::section {
                    background-color: #f5f5f5;
                    padding: 5px;
                    border: none;
                    border-right: 1px solid #ddd;
                    border-bottom: 1px solid #ddd;
                }
            """)
            
            list_container.addWidget(self.file_list)
            right_section.addLayout(list_container, stretch=1)
            
            # 작성 완료 버튼
            self.complete_btn = QPushButton('작성 완료')
            self.complete_btn.setStyleSheet("""
                QPushButton {
                    padding: 10px;
                    background-color: #fe3c72;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #f28cb1;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                }
            """)
            self.complete_btn.clicked.connect(self.complete_annotation)
            right_section.addWidget(self.complete_btn)
            
            return right_section
            
        except Exception as e:
            logger.error(f"Error initializing right section: {str(e)}")
            raise

    def keyPressEvent(self, event):
        """키보드 이벤트 처리"""
        try:
            if event.key() == self.play_shortcut:
                self.toggle_play()
            elif event.key() == self.prev_sec_shortcut and not event.modifiers() & Qt.ControlModifier:
                self.move_second(-1)
            elif event.key() == self.next_sec_shortcut and not event.modifiers() & Qt.ControlModifier:
                self.move_second(1)
            elif event.key() == self.prev_frame_shortcut and event.modifiers() & Qt.ControlModifier:
                self.move_frame(-1)
            elif event.key() == self.next_frame_shortcut and event.modifiers() & Qt.ControlModifier:
                self.move_frame(1)
            elif event.key() == self.mark_shortcut:
                self.mark_segment()
                
        except Exception as e:
            logger.error(f"Error handling key press: {str(e)}")

    def toggle_play(self):
        """재생/일시정지 전환"""
        try:
            if not self.cap:
                return
                
            self.is_playing = not self.is_playing
            if self.is_playing:
                self.play_btn.setText('일시정지')
                self.timer.start(int(1000 / self.fps))  # fps에 맞춰 타이머 간격 설정
            else:
                self.play_btn.setText('재생')
                self.timer.stop()
                
        except Exception as e:
            logger.error(f"Error toggling play state: {str(e)}")

    def move_frame(self, delta):
        """프레임 단위 이동"""
        try:
            if not self.cap:
                return
                
            target_frame = self.current_frame + delta
            if 0 <= target_frame < self.total_frames:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                self.update_frame()
                
        except Exception as e:
            logger.error(f"Error moving frame: {str(e)}")

    def move_second(self, seconds):
        """초 단위 이동"""
        try:
            if not self.cap:
                return
                
            target_frame = self.current_frame + (seconds * self.fps)
            if 0 <= target_frame < self.total_frames:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                self.update_frame()
                
        except Exception as e:
            logger.error(f"Error moving second: {str(e)}")

    def update_frame(self):
        """현재 프레임 업데이트"""
        try:
            if self.cap is None or not self.cap.isOpened():
                logger.warning("Video capture is not initialized or opened")
                return

            ret, frame = self.cap.read()
            if not ret:
                # 마지막 프레임에 도달한 경우
                if self.current_frame >= self.total_frames - 1:
                    self.is_playing = False
                    self.timer.stop()
                    self.play_btn.setText('재생')
                    logger.info("Reached end of video")
                    return
                
                # 그 외의 경우 처음으로 되감기
                logger.info("Rewinding video to start")
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret:
                    raise Exception("Failed to read video frame after rewind")
            
            try:
                # OpenCV BGR to RGB 변환
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                
                # QImage 생성
                qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                # 비디오 레이블의 현재 크기 가져오기
                label_size = self.video_label.size()
                
                # 영상 비율을 유지하면서 최대한 큰 크기로 스케일링
                scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                    label_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                
                # 비디오 레이블 중앙에 표시
                self.video_label.setPixmap(scaled_pixmap)
                
                # 프레임 정보 업데이트
                self.current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1  # -1 because read() advances frame
                current_time = self.current_frame / self.fps
                total_time = self.total_frames / self.fps
                
                # 시간 표시 업데이트
                if self.total_frames > 0:  # 0으로 나누기 방지
                    self.time_label.setText(
                        f'프레임: {self.current_frame}/{self.total_frames} | '
                        f'시간: {current_time:.2f}/{total_time:.2f}s'
                    )

                # 슬라이더 업데이트
                self.video_slider.setMaximum(self.total_frames - 1)
                if not self.video_slider.isSliderDown():  # 드래그 중이 아닐 때만 업데이트
                    self.video_slider.setValue(self.current_frame)
                
                # 타임라인 업데이트
                if self.timeline:
                    self.timeline.set_current_frame(self.current_frame)
                    self.timeline.set_total_frames(self.total_frames)
                    self.timeline.update()
                    
                logger.debug(f"Frame updated: {self.current_frame}/{self.total_frames}")
                
            except cv2.error as e:
                logger.error(f"OpenCV error while processing frame: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Error updating frame: {str(e)}", exc_info=True)
            self.stop_playback()
            QMessageBox.critical(self, '오류', f'프레임 업데이트 실패: {str(e)}')

    def slider_pressed(self):
        """슬라이더 드래그 시작"""
        try:
            if self.is_playing:
                self.toggle_play()  # 재생 중이면 일시정지
        except Exception as e:
            logger.error(f"Error in slider_pressed: {str(e)}")

    def slider_moved(self):
        """슬라이더 이동 중"""
        try:
            if self.cap:
                frame = self.video_slider.value()
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
                self.update_frame()
        except Exception as e:
            logger.error(f"Error in slider_moved: {str(e)}")

    def slider_released(self):
        """슬라이더 드래그 종료"""
        try:
            if self.cap:
                frame = self.video_slider.value()
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
                self.update_frame()
        except Exception as e:
            logger.error(f"Error in slider_released: {str(e)}")

    def stop_playback(self):
        """재생 중지 및 리소스 정리"""
        try:
            self.is_playing = False
            self.timer.stop()
            self.play_btn.setText('재생')
            
            if self.cap is not None:
                self.cap.release()
                self.cap = None
                
            self.enable_video_controls(False)
            
        except Exception as e:
            logger.error(f"Error stopping playback: {str(e)}")

    def load_path(self):        
        """경로로부터 비디오 파일 로드"""
        try:
            path = self.path_input.text().strip()
            if not path:
                QMessageBox.warning(self, '경고', '경로를 입력해주세요.')
                return
                
            path = Path(path)
            if not path.exists():
                raise FileNotFoundError('경로를 찾을 수 없습니다.')
                
            self.load_video_files(path)
            
        except Exception as e:
            logger.error(f"Error loading path: {str(e)}")
            QMessageBox.critical(self, '오류', f'경로 로드 실패: {str(e)}')

    def load_directory(self):
        """폴더 선택 다이얼로그를 통한 비디오 파일 로드"""
        try:
            dir_path = QFileDialog.getExistingDirectory(
                self, 
                '폴더 선택',
                "",
                QFileDialog.ShowDirsOnly
            )
            if dir_path:
                self.load_video_files(Path(dir_path))
                
        except Exception as e:
            logger.error(f"Error loading directory: {str(e)}")
            QMessageBox.critical(self, '오류', f'폴더 로드 실패: {str(e)}')

    def load_files(self):
        """파일 선택 다이얼로그를 통한 비디오 파일 로드"""
        try:
            files, _ = QFileDialog.getOpenFileNames(
                self,
                '비디오 파일 선택',
                "",
                'Video Files (*.mp4 *.avi *.mov *.mkv)'
            )
            if files:
                self.add_video_files([Path(f) for f in files])
                
        except Exception as e:
            logger.error(f"Error loading files: {str(e)}")
            QMessageBox.critical(self, '오류', f'파일 로드 실패: {str(e)}')

    def load_video_files(self, path):
        """비디오 파일 목록 로드"""
        try:
            video_files = []
            if path.is_file():
                if self.is_video_file(path):
                    video_files.append(path)
            else:
                for file in path.rglob('*'):
                    if self.is_video_file(file):
                        video_files.append(file)
                        
            if not video_files:
                QMessageBox.warning(self, '경고', '비디오 파일을 찾을 수 없습니다.')
                return
                
            self.add_video_files(video_files)
            
        except Exception as e:
            logger.error(f"Error loading video files: {str(e)}")
            raise

    def is_video_file(self, path):
        """비디오 파일 여부 확인"""
        return path.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv']

    def add_video_files(self, files):
        """비디오 파일 목록에 파일 추가"""
        try:
            # 중복 제거
            existing_paths = {str(f) for f in self.current_files}
            new_files = [f for f in files if str(f) not in existing_paths]
            
            if new_files:
                self.current_files.extend(new_files)
                self.update_file_list()
                
        except Exception as e:
            logger.error(f"Error adding video files: {str(e)}")
            raise

    def update_file_list(self):
        """파일 목록 테이블 업데이트"""
        try:
            # 테이블 기본 설정
            self.file_list.setRowCount(len(self.current_files))
            self.file_list.setColumnWidth(0, 200)  # 파일명 열 너비
            self.file_list.setColumnWidth(1, 40)   # 상태 열 너비
            
            # 마지막 열 고정 크기 설정
            self.file_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
            self.file_list.setColumnWidth(2, 80)   # 버튼 열 너비를 80으로 증가
            
            for i, file in enumerate(self.current_files):
                # 행 높이 설정
                self.file_list.setRowHeight(i, 30)  # 행 높이를 30으로 증가
                
                # 파일명
                name_item = QTableWidgetItem(file.name)
                name_item.setToolTip(str(file))
                self.file_list.setItem(i, 0, name_item)
                
                # 상태 (어노테이션 존재 여부)
                json_path = file.with_suffix('.json')
                status_item = QTableWidgetItem()
                if json_path.exists():
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if ('meta_data' in data and 'annotations' in data and 
                                'segmentation' in data['annotations']):
                                status_item.setText('✓')
                    except:
                        pass
                status_item.setTextAlignment(Qt.AlignCenter)
                self.file_list.setItem(i, 1, status_item)
                
                # 현재 실행 중인 파일 행 색상 변경
                if i == self.current_file_index:
                    for col in range(3):
                        item = self.file_list.item(i, col)
                        if item:
                            item.setBackground(QBrush(QColor("#f28cb1")))
                
                # 로드 버튼
                if i != self.current_file_index:
                    container = QWidget()
                    container_layout = QHBoxLayout(container)
                    container_layout.setContentsMargins(5, 0, 5, 0)
                    container_layout.setSpacing(0)
                    
                    load_btn = QPushButton('로드')
                    load_btn.setFixedSize(60, 24)
                    load_btn.setStyleSheet("""
                        QPushButton {
                            border: 1px solid #ddd;
                            border-radius: 3px;
                            background-color: white;
                            padding: 0px;
                        }
                        QPushButton:hover {
                            background-color: #f0f0f0;
                        }
                        QPushButton:pressed {
                            background-color: #e0e0e0;
                        }
                    """)
                    load_btn.clicked.connect(lambda x, idx=i: self.load_video(idx))
                    
                    container_layout.addWidget(load_btn, alignment=Qt.AlignCenter)
                    self.file_list.setCellWidget(i, 2, container)
                else:
                    current_item = QTableWidgetItem('현재 파일')
                    current_item.setTextAlignment(Qt.AlignCenter)
                    current_item.setForeground(QBrush(QColor("#ffffff")))
                    self.file_list.setItem(i, 2, current_item)
                    
        except Exception as e:
            logger.error(f"Error updating file list: {str(e)}")
            raise

    def load_video(self, index):
        """선택한 비디오 파일 로드"""
        try:
            logger.info(f"Loading video at index {index}")
            
            # 저장되지 않은 변경사항 확인
            if self.has_unsaved_changes:
                reply = QMessageBox.question(
                    self,
                    '확인',
                    '저장되지 않은 변경사항이 있습니다. 저장하시겠습니까?',
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                
                if reply == QMessageBox.Cancel:
                    return
                elif reply == QMessageBox.Yes:
                    self.save_annotations()

            file_path = self.current_files[index]
            
            # 기존 비디오 캡처 해제
            if self.cap is not None:
                self.cap.release()
                self.cap = None

            # 세그먼트와 타임라인 초기화
            self.segments = []
            if self.timeline:
                self.timeline.segments = []
                self.timeline.update()
            
            # 파일 존재 확인
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # VideoCapture 생성
            self.cap = cv2.VideoCapture(str(file_path))
            
            if not self.cap.isOpened():
                raise Exception("Failed to open video file")
            
            # 비디오 정보 가져오기
            self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            if self.fps <= 0:
                self.fps = 15  # 기본값 설정
                
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.current_frame = 0
            self.current_file_index = index
            
            # 첫 프레임 테스트
            ret, test_frame = self.cap.read()
            if not ret or test_frame is None:
                raise Exception("Failed to read first frame")
            
            # 처음으로 되감기
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            # UI 업데이트
            self.enable_video_controls(True)
            self.update_frame()
            self.update_file_list()
            
            # 어노테이션 로드
            self.load_annotations()
            
            # 변경사항 초기화
            self.has_unsaved_changes = False
            
            logger.info("Video loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading video: {str(e)}", exc_info=True)
            self.stop_playback()
            QMessageBox.critical(self, '오류', f'비디오 로드 실패: {str(e)}')

    def load_annotations(self):
        """어노테이션 파일 로드"""
        try:
            if self.current_file_index < 0:
                return

            json_path = self.current_files[self.current_file_index].with_suffix('.json')
            if json_path.exists():
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    # 필요한 키들이 모두 있는지 확인
                    if ('meta_data' in data and 'annotations' in data and 
                        'segmentation' in data['annotations']):
                        
                        self.segments = []
                        for seg in data['annotations'].get('segmentation', []):
                            if all(key in seg for key in ['start_frame', 'end_frame', 'action_type']):
                                segment = VideoSegment(
                                    seg['start_frame'],
                                    seg['end_frame'],
                                    seg['action_type']
                                )
                                segment.duration = seg.get('duration', 
                                    segment.end_frame - segment.start_frame)
                                segment.keyframe = seg.get('keyframe', 
                                    (segment.start_frame + segment.end_frame) // 2)
                                segment.keypoints = seg.get('keypoints', [])
                                self.segments.append(segment)

                        if 'user_num' in data['annotations']:
                            self.user_num_spin.setValue(data['annotations']['user_num'])

                        logger.info(f"Loaded {len(self.segments)} segments from {json_path}")
                    else:
                        self.segments = []
                        logger.info("Invalid JSON structure")

                except json.JSONDecodeError as e:
                    logger.error(f"Error loading annotations: {str(e)}")
                    self.segments = []
                except Exception as e:
                    logger.error(f"Error processing annotations: {str(e)}")
                    self.segments = []
            else:
                self.segments = []

            # Timeline 업데이트
            if self.timeline:
                self.timeline.segments = self.segments
                self.timeline.update()

        except Exception as e:
            logger.error(f"Error in load_annotations: {str(e)}")
            self.segments = []

    def load_annotations(self):
        """어노테이션 파일 로드"""
        try:
            if self.current_file_index < 0:
                return

            json_path = self.current_files[self.current_file_index].with_suffix('.json')
            if not json_path.exists():
                logger.info(f"No annotation file exists: {json_path}")
                self.segments = []
                return

            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 데이터 구조 검증
                required_keys = ['meta_data', 'additional_info', 'annotations']
                if not all(key in data for key in required_keys):
                    logger.error("Missing required keys in JSON data")
                    self.segments = []
                    return

                annotations = data['annotations']
                if 'segmentation' not in annotations:
                    logger.error("Missing segmentation data in annotations")
                    self.segments = []
                    return

                # 세그먼트 데이터 로드
                self.segments = []
                for seg in annotations['segmentation']:
                    try:
                        required_seg_keys = ['start_frame', 'end_frame', 'action_type', 'duration', 'keyframe']
                        if not all(key in seg for key in required_seg_keys):
                            logger.warning(f"Skipping segment due to missing keys: {seg}")
                            continue

                        segment = VideoSegment(
                            seg['start_frame'],
                            seg['end_frame'],
                            seg['action_type']
                        )
                        segment.duration = seg['duration']
                        segment.keyframe = seg['keyframe']
                        segment.keypoints = seg.get('keypoints', [])
                        self.segments.append(segment)
                    except Exception as e:
                        logger.error(f"Error processing segment: {str(e)}")
                        continue

                # user_num 설정
                if 'user_num' in annotations:
                    self.user_num_spin.setValue(annotations['user_num'])

                logger.info(f"Loaded {len(self.segments)} segments from {json_path}")

                # Timeline 업데이트
                if self.timeline:
                    self.timeline.segments = self.segments
                    self.timeline.update()

            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON file: {str(e)}")
                self.segments = []
            except Exception as e:
                logger.error(f"Error loading annotations: {str(e)}")
                self.segments = []

        except Exception as e:
            logger.error(f"Error in load_annotations: {str(e)}")
            self.segments = []

    # VideoLabeler의 mark_segment 메서드 수정
    def mark_segment(self):
        """구간 표시 처리"""
        try:
            if not self.cap:
                return
                    
            if not self.marking_segment:
                # 구간 시작
                self.current_segment = VideoSegment(self.current_frame, self.current_frame)
                self.mark_btn.setText('구간 종료')
                self.marking_segment = True
                if self.timeline:
                    self.timeline.set_marking_start(self.current_frame)
            else:
                # 구간 종료
                if self.current_frame <= self.current_segment.start_frame:
                    QMessageBox.warning(self, '경고', '종료 지점은 시작 지점보다 뒤여야 합니다.')
                    return
                    
                self.current_segment.end_frame = self.current_frame
                self.current_segment.duration = self.current_segment.end_frame - self.current_segment.start_frame
                self.current_segment.keyframe = (self.current_segment.start_frame + self.current_segment.end_frame) // 2
                
                # 세그먼트 정보 입력 다이얼로그 표시
                dialog = SegmentDialog(self.current_segment, parent=self)
                if dialog.exec_():
                    self.segments.append(dialog.segment)
                    if self.timeline:
                        self.timeline.segments = self.segments
                        self.timeline.update()
                    self.has_unsaved_changes = True  # 저장 필요 표시
                    # 자동 저장 제거 - 작성 완료 버튼을 눌러야만 저장되도록 변경
                
                self.mark_btn.setText('구간 표시')
                self.marking_segment = False
                self.current_segment = None
                if self.timeline:
                    self.timeline.clear_marking_start()
                        
        except Exception as e:
            logger.error(f"Error marking segment: {str(e)}")

    def edit_segment(self, index):
        """세그먼트 편집"""
        try:
            logger.info(f"Editing segment at index {index}")
            if 0 <= index < len(self.segments):
                segment = self.segments[index]
                dialog = SegmentDialog(segment, editing=True, parent=self)
                
                if dialog.exec_():
                    if dialog.delete_requested:
                        # 세그먼트 삭제
                        self.segments.pop(index)
                        logger.info(f"Deleted segment at index {index}")
                    else:
                        # 세그먼트 업데이트
                        self.segments[index] = dialog.segment
                        # duration 재계산
                        self.segments[index].duration = (
                            self.segments[index].end_frame - self.segments[index].start_frame
                        )
                        logger.info(f"Updated segment at index {index}")
                    
                    self.has_unsaved_changes = True
                    self.save_annotations()  # 자동 저장
                    
                    # Timeline 업데이트
                    if self.timeline:
                        self.timeline.segments = self.segments
                        self.timeline.update()
                    
        except Exception as e:
            logger.error(f"Error editing segment: {str(e)}")
            QMessageBox.critical(self, '오류', f'세그먼트 편집 실패: {str(e)}')

    def save_annotations(self):
        """어노테이션 저장"""
        try:
            if self.current_file_index < 0:
                logger.warning("No file selected for saving annotations")
                return False

            file_path = self.current_files[self.current_file_index]
            json_path = file_path.with_suffix('.json')
            
            annotations_data = {
                'meta_data': {
                    'file_name': file_path.name,
                    'format': file_path.suffix[1:],
                    'size': file_path.stat().st_size,
                    'width_height': [
                        int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                        int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    ],
                    'environment': 0,
                    'frame_rate': self.fps,
                    'total_frames': self.total_frames,
                    'camera_height': 170,
                    'camera_angle': 15
                },
                'additional_info': {
                    'InteractionType': 'Touchscreen'
                },
                'annotations': {
                    'space_context': '',
                    'user_num': self.user_num_spin.value(),
                    'target_objects': [
                        {
                            'object_id': i,
                            'age': 1,
                            'gender': 1,
                            'disability': 2
                        } for i in range(self.user_num_spin.value())
                    ],
                    'segmentation': [
                        {
                            'segment_id': i,
                            'action_type': segment.action_type,
                            'start_frame': segment.start_frame,
                            'end_frame': segment.end_frame,
                            'duration': segment.duration,
                            'keyframe': segment.keyframe,
                            'keypoints': segment.keypoints
                        } for i, segment in enumerate(self.segments)
                    ]
                }
            }

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(annotations_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Successfully saved annotations to {json_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving annotations: {str(e)}")
            QMessageBox.critical(self, '오류', f'어노테이션 저장 실패: {str(e)}')
            return False        

    def complete_annotation(self):
        """어노테이션 작성 완료"""
        try:
            if not self.segments:
                QMessageBox.warning(self, '경고', '저장할 구간이 없습니다.')
                return
                    
            reply = QMessageBox.question(
                self,
                '확인',
                '작성을 완료하시겠습니까?',
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.save_annotations()
                self.has_unsaved_changes = False  # 여기에 추가
                QMessageBox.information(self, '완료', '어노테이션이 저장되었습니다.')
                    
        except Exception as e:
            logger.error(f"Error completing annotation: {str(e)}")
            QMessageBox.critical(self, '오류', f'작성 완료 실패: {str(e)}')

    def enable_video_controls(self, enable=True):
        """비디오 컨트롤 버튼들의 활성화/비활성화"""
        controls = [
            self.play_btn,
            self.prev_frame_btn,
            self.next_frame_btn,
            self.prev_sec_btn,
            self.next_sec_btn,
            self.mark_btn
        ]
        for control in controls:
            control.setEnabled(enable)

    def closeEvent(self, event):
        """프로그램 종료 시 처리"""
        try:
            if self.has_unsaved_changes:
                reply = QMessageBox.question(
                    self,
                    '확인',
                    '저장되지 않은 변경사항이 있습니다. 저장하시겠습니까?',
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                
                if reply == QMessageBox.Cancel:
                    event.ignore()
                    return
                elif reply == QMessageBox.Yes:
                    self.save_annotations()

            if self.cap:
                self.cap.release()
            event.accept()
            
        except Exception as e:
            logger.error(f"Error during close: {str(e)}")
            event.accept()

if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        
        # 스타일 설정
        app.setStyle('Fusion')
        
        window = VideoLabeler()
        window.show()
        
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.error(f"Application error: {str(e)}", exc_info=True)
        sys.exit(1)