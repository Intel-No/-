import sys
import os
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QComboBox, QFileDialog, QSlider, QGroupBox)
from PyQt6.QtCore import Qt, QTimer

class DualTrackPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("双轨音频播放器")
        self.setMinimumSize(600, 400)
        
        # 音频文件和设备变量
        self.vocal_file = None
        self.instrumental_file = None
        self.vocal_data = None
        self.instrumental_data = None
        self.sample_rate = None
        self.is_playing = False
        self.is_paused = False
        self.current_frame = 0
        self.play_thread = None
        
        # 创建主界面
        self.init_ui()
        
        # 检测音频设备
        self.detect_audio_devices()
        
    def init_ui(self):
        # 创建中央部件和主布局
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # 文件上传区
        upload_group = QGroupBox("音频文件上传")
        upload_layout = QVBoxLayout()
        
        # 原声轨道上传
        vocal_layout = QHBoxLayout()
        self.vocal_label = QLabel("原声轨道: 未选择文件")
        vocal_upload_btn = QPushButton("选择文件")
        vocal_upload_btn.clicked.connect(lambda: self.upload_file("vocal"))
        vocal_layout.addWidget(self.vocal_label)
        vocal_layout.addWidget(vocal_upload_btn)
        
        # 伴奏轨道上传
        instrumental_layout = QHBoxLayout()
        self.instrumental_label = QLabel("伴奏轨道: 未选择文件")
        instrumental_upload_btn = QPushButton("选择文件")
        instrumental_upload_btn.clicked.connect(lambda: self.upload_file("instrumental"))
        instrumental_layout.addWidget(self.instrumental_label)
        instrumental_layout.addWidget(instrumental_upload_btn)
        
        upload_layout.addLayout(vocal_layout)
        upload_layout.addLayout(instrumental_layout)
        upload_group.setLayout(upload_layout)
        
        # 设备选择区
        device_group = QGroupBox("音频设备选择")
        device_layout = QVBoxLayout()
        
        # 原声轨道设备选择
        vocal_device_layout = QHBoxLayout()
        vocal_device_layout.addWidget(QLabel("原声轨道设备:"))
        self.vocal_device_combo = QComboBox()
        vocal_device_layout.addWidget(self.vocal_device_combo)
        
        # 伴奏轨道设备选择
        instrumental_device_layout = QHBoxLayout()
        instrumental_device_layout.addWidget(QLabel("伴奏轨道设备:"))
        self.instrumental_device_combo = QComboBox()
        instrumental_device_layout.addWidget(self.instrumental_device_combo)
        
        device_layout.addLayout(vocal_device_layout)
        device_layout.addLayout(instrumental_device_layout)
        device_group.setLayout(device_layout)
        
        # 音量控制区
        volume_group = QGroupBox("音量控制")
        volume_layout = QVBoxLayout()
        
        # 原声轨道音量
        vocal_volume_layout = QHBoxLayout()
        vocal_volume_layout.addWidget(QLabel("原声音量:"))
        self.vocal_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.vocal_volume_slider.setRange(0, 100)
        self.vocal_volume_slider.setValue(100)
        vocal_volume_layout.addWidget(self.vocal_volume_slider)
        
        # 伴奏轨道音量
        instrumental_volume_layout = QHBoxLayout()
        instrumental_volume_layout.addWidget(QLabel("伴奏音量:"))
        self.instrumental_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.instrumental_volume_slider.setRange(0, 100)
        self.instrumental_volume_slider.setValue(100)
        instrumental_volume_layout.addWidget(self.instrumental_volume_slider)
        
        volume_layout.addLayout(vocal_volume_layout)
        volume_layout.addLayout(instrumental_volume_layout)
        volume_group.setLayout(volume_layout)
        
        # 播放控制区
        control_group = QGroupBox("播放控制")
        control_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("播放")
        self.pause_btn = QPushButton("暂停")
        self.stop_btn = QPushButton("停止")
        
        self.play_btn.clicked.connect(self.play_audio)
        self.pause_btn.clicked.connect(self.pause_audio)
        self.stop_btn.clicked.connect(self.stop_audio)
        
        # 初始状态下，暂停和停止按钮不可用
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.stop_btn)
        control_group.setLayout(control_layout)
        
        # 添加所有组件到主布局
        main_layout.addWidget(upload_group)
        main_layout.addWidget(device_group)
        main_layout.addWidget(volume_group)
        main_layout.addWidget(control_group)
        
        self.setCentralWidget(central_widget)
    
    def detect_audio_devices(self):
        """检测可用的音频设备"""
        devices = sd.query_devices()
        output_devices = []
        
        for i, device in enumerate(devices):
            # 只添加输出设备
            if device['max_output_channels'] > 0:
                name = f"{device['name']} (输出通道: {device['max_output_channels']})"
                output_devices.append((i, name))
        
        # 清空并添加设备到下拉菜单
        self.vocal_device_combo.clear()
        self.instrumental_device_combo.clear()
        
        for idx, name in output_devices:
            self.vocal_device_combo.addItem(name, idx)
            self.instrumental_device_combo.addItem(name, idx)
        
        # 如果有多个设备，默认选择不同的设备
        if len(output_devices) > 1:
            self.instrumental_device_combo.setCurrentIndex(1)
    
    def upload_file(self, track_type):
        """上传音频文件"""
        file_dialog = QFileDialog()
        file_dialog.setNameFilter("音频文件 (*.mp3 *.wav)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        
        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]
            file_name = os.path.basename(file_path)
            
            if track_type == "vocal":
                self.vocal_file = file_path
                self.vocal_label.setText(f"原声轨道: {file_name}")
            else:  # instrumental
                self.instrumental_file = file_path
                self.instrumental_label.setText(f"伴奏轨道: {file_name}")
            
            # 检查是否可以启用播放按钮
            self.check_play_button_state()
    
    def check_play_button_state(self):
        """检查是否可以启用播放按钮"""
        if self.vocal_file and self.instrumental_file:
            self.play_btn.setEnabled(True)
        else:
            self.play_btn.setEnabled(False)
    
    def load_audio_files(self):
        """加载音频文件"""
        try:
            # 加载原声轨道
            vocal_data, vocal_sr = sf.read(self.vocal_file, dtype='float32')
            # 加载伴奏轨道
            instrumental_data, instrumental_sr = sf.read(self.instrumental_file, dtype='float32')
            
            # 确保两个文件的采样率相同
            if vocal_sr != instrumental_sr:
                # 简单处理：使用第一个文件的采样率
                print(f"警告：两个文件的采样率不同 ({vocal_sr} vs {instrumental_sr})，使用原声轨道的采样率")
                self.sample_rate = vocal_sr
            else:
                self.sample_rate = vocal_sr
            
            # 确保数据是二维的 (单声道转为二维)
            if vocal_data.ndim == 1:
                vocal_data = vocal_data.reshape(-1, 1)
            if instrumental_data.ndim == 1:
                instrumental_data = instrumental_data.reshape(-1, 1)
            
            # 确保两个文件的长度相同
            min_length = min(len(vocal_data), len(instrumental_data))
            self.vocal_data = vocal_data[:min_length]
            self.instrumental_data = instrumental_data[:min_length]
            
            return True
        except Exception as e:
            print(f"加载音频文件时出错: {e}")
            return False
    
    def play_audio(self):
        """播放音频"""
        if self.is_paused:  # 如果是从暂停状态恢复
            self.is_paused = False
            self.is_playing = True
            self.play_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            # 创建新线程继续播放
            self.play_thread = threading.Thread(target=self.play_audio_thread)
            self.play_thread.daemon = True
            self.play_thread.start()
            return
        
        # 加载音频文件
        if not self.load_audio_files():
            return
        
        # 重置播放状态
        self.current_frame = 0
        self.is_playing = True
        self.is_paused = False
        
        # 更新按钮状态
        self.play_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        
        # 创建播放线程
        self.play_thread = threading.Thread(target=self.play_audio_thread)
        self.play_thread.daemon = True
        self.play_thread.start()
    
    def play_audio_thread(self):
        """在单独的线程中播放音频"""
        try:
            # 获取选定的设备索引
            vocal_device_idx = self.vocal_device_combo.currentData()
            instrumental_device_idx = self.instrumental_device_combo.currentData()
            
            # 创建两个输出流
            vocal_stream = sd.OutputStream(
                samplerate=self.sample_rate,
                device=vocal_device_idx,
                channels=self.vocal_data.shape[1],
                dtype='float32'
            )
            
            instrumental_stream = sd.OutputStream(
                samplerate=self.sample_rate,
                device=instrumental_device_idx,
                channels=self.instrumental_data.shape[1],
                dtype='float32'
            )
            
            # 打开流
            vocal_stream.start()
            instrumental_stream.start()
            
            # 设置缓冲区大小
            buffer_size = 1024
            
            # 播放循环
            while self.is_playing and self.current_frame < len(self.vocal_data):
                if not self.is_paused:
                    # 计算剩余帧数
                    frames_left = len(self.vocal_data) - self.current_frame
                    current_buffer_size = min(buffer_size, frames_left)
                    
                    # 获取当前缓冲区的音频数据
                    vocal_buffer = self.vocal_data[self.current_frame:self.current_frame + current_buffer_size]
                    instrumental_buffer = self.instrumental_data[self.current_frame:self.current_frame + current_buffer_size]
                    
                    # 应用音量控制
                    vocal_volume = self.vocal_volume_slider.value() / 100.0
                    instrumental_volume = self.instrumental_volume_slider.value() / 100.0
                    
                    vocal_buffer = vocal_buffer * vocal_volume
                    instrumental_buffer = instrumental_buffer * instrumental_volume
                    
                    # 写入音频数据到流
                    vocal_stream.write(vocal_buffer)
                    instrumental_stream.write(instrumental_buffer)
                    
                    # 更新当前帧位置
                    self.current_frame += current_buffer_size
                
                # 短暂休眠，减少CPU使用率
                threading.Event().wait(0.01)
            
            # 关闭流
            vocal_stream.stop()
            instrumental_stream.stop()
            vocal_stream.close()
            instrumental_stream.close()
            
            # 如果播放完成（而不是被停止），重置状态
            if self.current_frame >= len(self.vocal_data) and self.is_playing:
                self.is_playing = False
                # 使用QTimer在主线程中更新UI
                QTimer.singleShot(0, self.reset_ui_after_playback)
        
        except Exception as e:
            print(f"播放音频时出错: {e}")
            self.is_playing = False
            self.is_paused = False
            # 使用QTimer在主线程中更新UI
            QTimer.singleShot(0, self.reset_ui_after_playback)
    
    def pause_audio(self):
        """暂停音频播放"""
        if self.is_playing and not self.is_paused:
            self.is_paused = True
            self.play_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
    
    def stop_audio(self):
        """停止音频播放"""
        self.is_playing = False
        self.is_paused = False
        self.current_frame = 0
        # 更新UI状态
        self.reset_ui_after_playback()
    
    def reset_ui_after_playback(self):
        """重置UI状态"""
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)


def main():
    app = QApplication(sys.argv)
    player = DualTrackPlayer()
    player.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()