import streamlit as st
import os
from io import BytesIO
import subprocess
import wave
import zipfile
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import spectrogram as scipy_spectrogram

# ==================== 1. 配置与初始化 ====================

st.set_page_config(
    page_title="音频处理工具箱 Pro",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== 2. 辅助函数 ====================

def get_audio_info(file_path):
    """获取音频文件信息"""
    try:
        if file_path.endswith('.pcm'):
            return None, None, None, None  # PCM需要手动指定
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-show_entries', 'stream=sample_rate,channels,codec_name', '-of', 'json', file_path],
            capture_output=True, text=True
        )
        import json
        info = json.loads(result.stdout)
        duration = float(info['format']['duration'])
        stream = info['streams'][0]
        sample_rate = int(stream['sample_rate'])
        channels = int(stream['channels'])
        codec = stream['codec_name']
        return duration, sample_rate, channels, codec
    except:
        return None, None, None, None

def convert_audio(input_path, output_path, target_format='wav', target_sr=16000, target_channels=1):
    """使用ffmpeg转换音频"""
    codec_map = {
        'wav': 'pcm_s16le',
        'pcm': 'pcm_s16le',
        'mp3': 'libmp3lame',
        'm4a': 'aac'
    }
    
    codec = codec_map.get(target_format, 'pcm_s16le')
    
    command = ['ffmpeg', '-i', input_path]
    
    if target_format == 'pcm':
        # PCM输出需要特殊处理
        command.extend(['-f', 's16le', '-acodec', codec])
    else:
        command.extend(['-acodec', codec])
    
    command.extend([
        '-ar', str(target_sr),
        '-ac', str(target_channels),
        '-y', output_path
    ])
    
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def pcm_to_wav_buffer(pcm_data, sample_rate=16000, channels=1):
    """将PCM数据转换为WAV格式的BytesIO"""
    wav_buffer = BytesIO()
    with wave.open(wav_buffer, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    wav_buffer.seek(0)
    return wav_buffer

# ==================== 3. 主页面布局 ====================

st.title("🎵 音频处理工具箱 Pro")
st.markdown("---")

# 文件上传
uploaded_files = st.file_uploader(
    "上传音频文件 (支持: WAV, MP3, M4A, PCM 等常见格式)",
    type=["wav", "mp3", "m4a", "pcm", "flac", "ogg", "aac"],
    accept_multiple_files=True,
    key="audio_upload"
)

if uploaded_files:
    st.success(f"✅ 已选择 {len(uploaded_files)} 个文件")
    
    # 处理参数设置
    st.subheader(" 输出设置")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        output_format = st.selectbox(
            "输出格式",
            ["WAV", "PCM", "MP3", "M4A"],
            index=0,
            key="output_format"
        )
    with col2:
        output_sr = st.selectbox(
            "采样率 (Hz)",
            [8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000],
            index=2,
            key="output_sr"
        )
    with col3:
        output_channels = st.selectbox(
            "声道数",
            [1, 2],
            index=0,
            key="output_channels"
        )
    
    # PCM文件需要额外参数
    pcm_params = {}
    if any(f.name.endswith('.pcm') for f in uploaded_files):
        st.caption("⚠️ PCM文件需要指定原始参数")
        col1, col2 = st.columns(2)
        with col1:
            pcm_params['sample_rate'] = st.number_input("PCM原始采样率 (Hz)", value=16000, step=1000, key="pcm_sr")
        with col2:
            pcm_params['channels'] = st.number_input("PCM原始声道数", value=1, min_value=1, max_value=2, key="pcm_ch")
    
    st.divider()
    
    # 裁剪设置
    st.subheader("️ 音频裁剪 (可选)")
    enable_crop = st.checkbox("启用裁剪", key="enable_crop")
    
    if enable_crop:
        col1, col2 = st.columns(2)
        with col1:
            crop_start = st.number_input("裁剪起点 (秒)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="crop_start")
        with col2:
            crop_end = st.number_input("裁剪终点 (秒)", min_value=0.0, value=10.0, step=0.01, format="%.2f", key="crop_end")
        
        if crop_start >= crop_end:
            st.warning("⚠️ 起点必须小于终点")
    
    st.divider()
    
    # 操作按钮
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        play_all = st.button("▶️ 播放全部音频", type="secondary", key="play_all")
    with col2:
        convert_all = st.button("🚀 转换并下载", type="primary", key="convert_all")
    with col3:
        if st.button("🔄 重置", key="reset_all"):
            st.rerun()
    
    # ==================== 播放功能 ====================
    if play_all:
        st.subheader("🎧 音频播放")
        
        for idx, audio_file in enumerate(uploaded_files):
            st.markdown(f"**文件 {idx+1}: {audio_file.name}**")
            
            try:
                # 保存临时文件
                temp_path = f"temp_{audio_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(audio_file.getbuffer())
                
                # PCM特殊处理
                if audio_file.name.endswith('.pcm'):
                    pcm_data = audio_file.getbuffer()
                    sr = pcm_params.get('sample_rate', 16000)
                    ch = pcm_params.get('channels', 1)
                    
                    # 转换为WAV播放
                    wav_buf = pcm_to_wav_buffer(pcm_data, sr, ch)
                    st.audio(wav_buf, format="audio/wav")
                    
                    duration = len(pcm_data) / (sr * ch * 2)
                    st.info(f"📊 时长: {duration:.2f}秒 | 采样率: {sr}Hz | 声道: {ch}")
                else:
                    # 其他格式直接播放
                    st.audio(temp_path)
                    
                    # 获取音频信息
                    duration, sr, ch, codec = get_audio_info(temp_path)
                    if duration:
                        st.info(f"📊 时长: {duration:.2f}秒 | 采样率: {sr}Hz | 声道: {ch} | 编码: {codec}")
                
                # 清理临时文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
            except Exception as e:
                st.error(f"❌ 播放失败: {str(e)}")
            
            st.markdown("---")
    
    # ==================== 转换功能 ====================
    if convert_all:
        if enable_crop and crop_start >= crop_end:
            st.error("❌ 请先修正裁剪时间!")
        else:
            st.subheader("🔄 处理进度")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            converted_files = []
            failed_files = []
            
            for idx, audio_file in enumerate(uploaded_files):
                status_text.text(f"正在处理: {audio_file.name}")
                
                input_path = f"temp_input_{audio_file.name}"
                output_ext = output_format.lower()
                base_name = os.path.splitext(audio_file.name)[0]
                output_path = f"temp_output_{base_name}.{output_ext}"
                
                try:
                    # 保存上传文件
                    with open(input_path, "wb") as f:
                        f.write(audio_file.getbuffer())
                    
                    # 如果是裁剪模式,先裁剪
                    if enable_crop:
                        if audio_file.name.endswith('.pcm'):
                            # PCM裁剪
                            sr = pcm_params.get('sample_rate', 16000)
                            ch = pcm_params.get('channels', 1)
                            pcm_data = audio_file.getbuffer()
                            
                            start_byte = int(crop_start * sr * ch * 2)
                            end_byte = int(crop_end * sr * ch * 2)
                            start_byte = start_byte - (start_byte % 2)
                            end_byte = end_byte - (end_byte % 2)
                            
                            cropped_pcm = pcm_data[start_byte:end_byte]
                            
                            # 保存裁剪后的PCM
                            with open(input_path, "wb") as f:
                                f.write(cropped_pcm)
                        else:
                            # 其他格式裁剪
                            crop_command = [
                                'ffmpeg', '-i', input_path,
                                '-ss', str(crop_start),
                                '-to', str(crop_end),
                                '-y', f"temp_cropped_{audio_file.name}"
                            ]
                            subprocess.run(crop_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            input_path = f"temp_cropped_{audio_file.name}"
                    
                    # 转换音频
                    if audio_file.name.endswith('.pcm') and output_format != 'PCM':
                        # PCM转其他格式,需要先转成WAV
                        sr = pcm_params.get('sample_rate', 16000)
                        ch = pcm_params.get('channels', 1)
                        
                        # 先转成WAV中间文件
                        wav_path = f"temp_intermediate.wav"
                        with wave.open(wav_path, 'wb') as wf:
                            wf.setnchannels(ch)
                            wf.setsampwidth(2)
                            wf.setframerate(sr)
                            with open(input_path, 'rb') as pf:
                                wf.writeframes(pf.read())
                        
                        convert_audio(wav_path, output_path, output_format.lower(), output_sr, output_channels)
                        if os.path.exists(wav_path):
                            os.remove(wav_path)
                    else:
                        convert_audio(input_path, output_path, output_format.lower(), output_sr, output_channels)
                    
                    # 读取输出文件
                    with open(output_path, 'rb') as f:
                        output_data = f.read()
                    
                    output_filename = f"{base_name}_converted.{output_ext}"
                    converted_files.append((output_filename, output_data))
                    
                except Exception as e:
                    failed_files.append((audio_file.name, str(e)))
                
                finally:
                    # 清理临时文件
                    for tmp in [input_path, output_path, f"temp_cropped_{audio_file.name}"]:
                        if os.path.exists(tmp):
                            os.remove(tmp)
                
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            progress_bar.empty()
            status_text.empty()
            
            # 显示结果
            if converted_files:
                st.success(f"✅ 成功处理 {len(converted_files)} 个文件")
                
                if len(converted_files) == 1:
                    # 单个文件直接下载
                    fname, fdata = converted_files[0]
                    st.download_button(
                        label=f"📥 下载 {fname}",
                        data=fdata,
                        file_name=fname,
                        mime="audio/wav" if output_format == "WAV" else "application/octet-stream",
                        key="download_single"
                    )
                else:
                    # 多个文件打包ZIP
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for fname, fdata in converted_files:
                            zip_file.writestr(fname, fdata)
                    
                    st.download_button(
                        label="📥 下载全部结果 (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name=f"converted_{output_format.lower()}_files.zip",
                        mime="application/zip",
                        key="download_zip"
                    )
            
            if failed_files:
                st.warning(f"⚠️ {len(failed_files)} 个文件处理失败:")
                for fname, error in failed_files:
                    st.error(f"- {fname}: {error}")

# ==================== 底部信息 ====================

st.markdown("---")
st.caption("🎵 音频处理工具箱 Pro | 支持格式转换、采样率调整、声道转换、音频裁剪")
