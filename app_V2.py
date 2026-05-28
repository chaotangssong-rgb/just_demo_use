import streamlit as st
import os
from io import BytesIO
import subprocess
import wave
import zipfile

# ==================== 1. 配置与初始化 ====================

st.set_page_config(
    page_title="音频工具箱",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== 2. 主页面布局 ====================

st.title(" 音频工具箱")
st.markdown("---")

# 音频工具选择
audio_tool = st.radio(
    "选择音频转换工具",
    ["🎵 M4A → WAV", " WAV → PCM", "💿 PCM → WAV", "📉 48K → 16K"],
    horizontal=True
)

# ==================== 工具 1: M4A → WAV ====================

if audio_tool == "🎵 M4A → WAV":
    st.header("🎵 M4A 转 WAV")
    st.info("将 M4A 格式的音频文件转换为 WAV 格式(44100Hz, 立体声, 16bit)")
    
    m4a_files = st.file_uploader(
        "上传 M4A 文件",
        type=["m4a"],
        accept_multiple_files=True,
        key="m4a_upload_main"
    )
    
    if m4a_files:
        st.success(f"✅ 已选择 {len(m4a_files)} 个文件")
        
        if st.button("🚀 开始转换", type="primary", key="convert_m4a"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            converted_files = []
            failed_files = []
            
            for i, m4a_file in enumerate(m4a_files):
                status_text.text(f"正在转换: {m4a_file.name}")
                
                input_path = f"temp_{m4a_file.name}"
                output_path = os.path.splitext(input_path)[0] + ".wav"
                
                try:
                    # 保存上传的文件
                    with open(input_path, "wb") as f:
                        f.write(m4a_file.getbuffer())
                    
                    # 使用 ffmpeg 转换
                    command = [
                        'ffmpeg', '-i', input_path,
                        '-acodec', 'pcm_s16le',
                        '-ar', '44100',
                        '-y', output_path
                    ]
                    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    converted_files.append((os.path.splitext(m4a_file.name)[0] + ".wav", output_path))
                    
                except Exception as e:
                    failed_files.append((m4a_file.name, str(e)))
                
                finally:
                    # 清理临时文件
                    if os.path.exists(input_path):
                        os.remove(input_path)
                
                progress_bar.progress((i + 1) / len(m4a_files))
            
            progress_bar.empty()
            status_text.empty()
            
            # 显示结果
            if converted_files:
                st.success(f"✅ 成功转换 {len(converted_files)} 个文件")
                
                # 打包为 ZIP
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for fname, fpath in converted_files:
                        zip_file.write(fpath, fname)
                        os.remove(fpath)  # 清理转换后的文件
                
                st.download_button(
                    label="📥 下载全部结果 (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="converted_wav_files.zip",
                    mime="application/zip",
                    key="download_wav_zip"
                )
            
            if failed_files:
                st.warning(f"⚠️ {len(failed_files)} 个文件转换失败:")
                for fname, error in failed_files:
                    st.error(f"- {fname}: {error}")

# ==================== 工具 2: WAV → PCM ====================

elif audio_tool == " WAV → PCM":
    st.header("📻 WAV 转 PCM")
    st.info("将 WAV 格式转换为原始 PCM 数据(要求: 16KHz, 单声道, 16bit)")
    
    wav_files = st.file_uploader(
        "上传 WAV 文件",
        type=["wav"],
        accept_multiple_files=True,
        key="wav_upload_main"
    )
    
    if wav_files:
        st.success(f"✅ 已选择 {len(wav_files)} 个文件")
        
        if st.button("🚀 开始转换", type="primary", key="convert_wav"):
            converted_files = []
            failed_files = []
            
            for wav_file in wav_files:
                wav_path = f"temp_{wav_file.name}"
                
                try:
                    # 保存上传的文件
                    with open(wav_path, "wb") as f:
                        f.write(wav_file.getbuffer())
                    
                    # 检查音频格式
                    with wave.open(wav_path, 'rb') as wf:
                        if wf.getframerate() != 16000 or wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                            failed_files.append((wav_file.name, "不符合 16K/单通道/16bit 要求"))
                            continue
                        
                        # 读取 PCM 数据
                        pcm_data = wf.readframes(wf.getnframes())
                        pcm_filename = os.path.splitext(wav_file.name)[0] + ".pcm"
                        converted_files.append((pcm_filename, pcm_data))
                    
                except Exception as e:
                    failed_files.append((wav_file.name, str(e)))
                
                finally:
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
            
            # 显示结果
            if converted_files:
                st.success(f"✅ 成功转换 {len(converted_files)} 个文件")
                
                # 打包为 ZIP
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for fname, fdata in converted_files:
                        zip_file.writestr(fname, fdata)
                
                st.download_button(
                    label="📥 下载全部结果 (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="converted_pcm_files.zip",
                    mime="application/zip",
                    key="download_pcm_zip"
                )
            
            if failed_files:
                st.warning(f"⚠️ {len(failed_files)} 个文件转换失败:")
                for fname, error in failed_files:
                    st.error(f"- {fname}: {error}")

# ==================== 工具 3: PCM → WAV ====================

elif audio_tool == "💿 PCM → WAV":
    st.header("💿 PCM 转 WAV")
    st.info("将原始 PCM 音频数据封装为标准的 WAV 格式")
    
    pcm_files = st.file_uploader(
        "上传 PCM 文件",
        type=["pcm"],
        accept_multiple_files=True,
        key="pcm_upload_main"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        sample_rate = st.number_input("采样率 (Hz)", value=16000, step=1000, key="sample_rate_pcm")
    with col2:
        channels = st.number_input("声道数", value=1, min_value=1, max_value=2, key="channels_pcm")
    
    if pcm_files:
        st.success(f"✅ 已选择 {len(pcm_files)} 个文件")
        
        if st.button("🚀 开始转换", type="primary", key="convert_pcm"):
            converted_files = []
            failed_files = []
            
            for pcm_file in pcm_files:
                pcm_path = f"temp_{pcm_file.name}"
                
                try:
                    # 保存上传的文件
                    with open(pcm_path, "wb") as f:
                        f.write(pcm_file.getbuffer())
                    
                    # 转换为 WAV
                    wav_filename = os.path.splitext(pcm_file.name)[0] + ".wav"
                    wav_path = f"temp_{wav_filename}"
                    
                    with wave.open(wav_path, 'wb') as wf:
                        wf.setnchannels(channels)
                        wf.setsampwidth(2)
                        wf.setframerate(sample_rate)
                        with open(pcm_path, 'rb') as pf:
                            wf.writeframes(pf.read())
                    
                    converted_files.append((wav_filename, wav_path))
                    
                except Exception as e:
                    failed_files.append((pcm_file.name, str(e)))
                
                finally:
                    if os.path.exists(pcm_path):
                        os.remove(pcm_path)
            
            # 显示结果
            if converted_files:
                st.success(f"✅ 成功转换 {len(converted_files)} 个文件")
                
                # 打包为 ZIP
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for fname, fpath in converted_files:
                        zip_file.write(fpath, fname)
                        os.remove(fpath)
                
                st.download_button(
                    label=" 下载全部结果 (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="converted_wav_from_pcm.zip",
                    mime="application/zip",
                    key="download_wav_pcm_zip"
                )
            
            if failed_files:
                st.warning(f"⚠️ {len(failed_files)} 个文件转换失败:")
                for fname, error in failed_files:
                    st.error(f"- {fname}: {error}")

# ==================== 工具 4: 48K → 16K ====================

elif audio_tool == "📉 48K → 16K":
    st.header("📉 音频采样率转换")
    st.info("将音频文件从 48KHz 降采样到 16KHz (单声道, WAV格式)")
    
    audio_files = st.file_uploader(
        "上传音频文件",
        type=["wav", "m4a", "mp3"],
        accept_multiple_files=True,
        key="resample_upload_main"
    )
    
    if audio_files:
        st.success(f"✅ 已选择 {len(audio_files)} 个文件")
        
        if st.button("🚀 开始重采样", type="primary", key="resample_48k_16k"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            converted_files = []
            failed_files = []
            
            for i, audio_file in enumerate(audio_files):
                status_text.text(f"正在处理: {audio_file.name}")
                
                input_path = f"temp_{audio_file.name}"
                output_filename = f"16k_{os.path.splitext(audio_file.name)[0]}.wav"
                output_path = f"temp_{output_filename}"
                
                try:
                    # 保存上传的文件
                    with open(input_path, "wb") as f:
                        f.write(audio_file.getbuffer())
                    
                    # 使用 ffmpeg 重采样
                    command = [
                        'ffmpeg', '-i', input_path,
                        '-ar', '16000',
                        '-ac', '1',
                        '-y', output_path
                    ]
                    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    converted_files.append((output_filename, output_path))
                    
                except Exception as e:
                    failed_files.append((audio_file.name, str(e)))
                
                finally:
                    if os.path.exists(input_path):
                        os.remove(input_path)
                
                progress_bar.progress((i + 1) / len(audio_files))
            
            progress_bar.empty()
            status_text.empty()
            
            # 显示结果
            if converted_files:
                st.success(f"✅ 成功转换 {len(converted_files)} 个文件")
                
                # 打包为 ZIP
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for fname, fpath in converted_files:
                        zip_file.write(fpath, fname)
                        os.remove(fpath)
                
                st.download_button(
                    label=" 下载全部结果 (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="resampled_16k_files.zip",
                    mime="application/zip",
                    key="download_resampled_zip"
                )
            
            if failed_files:
                st.warning(f"⚠️ {len(failed_files)} 个文件转换失败:")
                for fname, error in failed_files:
                    st.error(f"- {fname}: {error}")

# ==================== 底部信息 ====================

st.markdown("---")
st.caption("🎵 音频工具箱 | 支持 M4A/WAV/PCM 格式互转及采样率转换")
