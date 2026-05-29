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
    st.subheader(" 音频裁剪 (可选)")
    enable_crop = st.checkbox("启用裁剪", key="enable_crop")
    
    if enable_crop:
        # 选择裁剪模式
        cut_mode = st.radio(
            "选择裁剪模式:",
            ["✂️ 只保留中间区域(删除两边)", "🗑️ 删除中间区域(保留两边)"],
            horizontal=True,
            key="cut_mode_radio"
        )
        
        if cut_mode == "✂️ 只保留中间区域(删除两边)":
            st.info(" 在波形图上查看时间坐标,设置要**保留**的区间,两侧将被删除")
        else:
            st.info(" 在波形图上查看时间坐标,设置要**删除**的区间,两侧将被保留并拼接")
        
        # 显示波形图(只显示第一个文件)
        st.subheader("📊 波形图 - 查看时间坐标")
        
        first_file = uploaded_files[0]
        try:
            # 保存临时文件
            temp_path = f"temp_waveform_{first_file.name}"
            with open(temp_path, "wb") as f:
                f.write(first_file.getbuffer())
            
            # 读取音频数据
            if first_file.name.endswith('.pcm'):
                # 转换为bytes类型
                pcm_data = bytes(first_file.getbuffer())
                sr = pcm_params.get('sample_rate', 16000)
                ch = pcm_params.get('channels', 1)
                pcm_array = np.frombuffer(pcm_data, dtype=np.int16)
                duration = len(pcm_array) / sr
            else:
                # 使用ffmpeg提取音频数据
                wav_path = f"temp_waveform.wav"
                subprocess.run(
                    ['ffmpeg', '-i', temp_path, '-f', 's16le', '-acodec', 'pcm_s16le', '-y', wav_path],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                with open(wav_path, 'rb') as f:
                    pcm_data = f.read()
                pcm_array = np.frombuffer(pcm_data, dtype=np.int16)
                
                # 获取音频信息
                duration, sr, ch, codec = get_audio_info(temp_path)
                if not duration:
                    duration = len(pcm_array) / 16000  # 默认
                
                if os.path.exists(wav_path):
                    os.remove(wav_path)
            
            # 绘制波形图
            fig, ax = plt.subplots(figsize=(14, 4))
            time_axis = np.arange(len(pcm_array)) / sr
            ax.plot(time_axis, pcm_array, linewidth=0.5, color='#1f77b4')
            ax.set_xlabel('时间 (秒)', fontsize=12)
            ax.set_ylabel('振幅', fontsize=12)
            ax.set_title(f'{first_file.name} - 波形图 (总时长: {duration:.2f}秒)', fontsize=14)
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()
            
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        except Exception as e:
            st.warning(f"️ 波形图显示失败: {str(e)}")
            duration = 10.0  # 默认值
        
        st.caption(" 提示: 上方波形图的横坐标即为时间(秒),请根据坐标设置裁剪时间")
        
        # 时间设置
        col1, col2 = st.columns(2)
        with col1:
            if cut_mode == "✂️ 只保留中间区域(删除两边)":
                label1 = "保留起点 (秒)"
            else:
                label1 = "删除起点 (秒)"
            
            crop_start = st.number_input(
                label1,
                min_value=0.0,
                max_value=duration if duration else 100.0,
                value=0.0,
                step=0.01,
                format="%.2f",
                key="crop_start"
            )
        with col2:
            if cut_mode == "✂️ 只保留中间区域(删除两边)":
                label2 = "保留终点 (秒)"
            else:
                label2 = "删除终点 (秒)"
            
            crop_end = st.number_input(
                label2,
                min_value=0.0,
                max_value=duration if duration else 100.0,
                value=duration if duration else 10.0,
                step=0.01,
                format="%.2f",
                key="crop_end"
            )
        
        if crop_start >= crop_end:
            st.warning("⚠️ 起点必须小于终点")
        else:
            # 显示调试信息
            with st.expander("🔍 查看时间对应关系(调试信息)"):
                st.write(f"📊 **音频信息**:")
                st.write(f"- 总时长: {duration:.2f}秒")
                if not first_file.name.endswith('.pcm'):
                    sr_info, ch_info = get_audio_info(temp_path)[:2] if 'temp_path' in locals() else (None, None)
                    if sr_info:
                        st.write(f"- 采样率: {sr_info}Hz")
                        st.write(f"- 声道数: {ch_info}")
                else:
                    st.write(f"- 采样率: {pcm_params.get('sample_rate', 16000)}Hz")
                    st.write(f"- 声道数: {pcm_params.get('channels', 1)}")
                
                st.write(f"")
                st.write(f"✂️ **裁剪设置**:")
                if cut_mode == "✂️ 只保留中间区域(删除两边)":
                    st.write(f"- 保留区间: {crop_start:.2f}s - {crop_end:.2f}s")
                    st.write(f"- 保留时长: {crop_end - crop_start:.2f}s")
                    st.write(f"- 删除部分: 0-{crop_start:.2f}s + {crop_end:.2f}s-{duration:.2f}s")
                else:
                    st.write(f"- 删除区间: {crop_start:.2f}s - {crop_end:.2f}s")
                    st.write(f"- 删除时长: {crop_end - crop_start:.2f}s")
                    st.write(f"- 保留部分: 0-{crop_start:.2f}s + {crop_end:.2f}s-{duration:.2f}s")
                
                st.write(f"")
                st.write(f"💡 **提示**: 波形图横坐标即为时间(秒),输入5.00就对应图中的5秒位置")
            
            if cut_mode == "✂️ 只保留中间区域(删除两边)":
                st.success(f"✅ 将保留: {crop_start:.2f}s - {crop_end:.2f}s (时长: {crop_end - crop_start:.2f}s)")
                st.info(f" 将删除: 0-{crop_start:.2f}s + {crop_end:.2f}s-{duration:.2f}s")
            else:
                st.success(f" 将删除: {crop_start:.2f}s - {crop_end:.2f}s (时长: {crop_end - crop_start:.2f}s)")
                st.info(f" 将保留: 0-{crop_start:.2f}s + {crop_end:.2f}s-{duration:.2f}s")
    
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
                    # 转换为bytes类型
                    pcm_data = bytes(audio_file.getbuffer())
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
                            # 转换为bytes类型(修复memoryview拼接错误)
                            pcm_data = bytes(audio_file.getbuffer())
                            
                            # 修复:时间 → 采样点索引 → 字节索引
                            start_sample_index = int(crop_start * sr)  # 采样点索引
                            end_sample_index = int(crop_end * sr)
                            
                            # 转换为字节索引(每个采样点2字节 × 声道数)
                            start_byte = start_sample_index * 2 * ch
                            end_byte = end_sample_index * 2 * ch
                            
                            # 确保字节对齐
                            start_byte = start_byte - (start_byte % 2)
                            end_byte = end_byte - (end_byte % 2)
                            
                            # 根据裁剪模式处理
                            if cut_mode == "✂️ 只保留中间区域(删除两边)":
                                # 只保留中间部分
                                cropped_pcm = pcm_data[start_byte:end_byte]
                            else:
                                # 删除中间,拼接两边
                                before_delete = pcm_data[:start_byte]
                                after_delete = pcm_data[end_byte:]
                                cropped_pcm = before_delete + after_delete
                            
                            # 保存裁剪后的PCM
                            with open(input_path, "wb") as f:
                                f.write(cropped_pcm)
                        else:
                            # 其他格式裁剪
                            if cut_mode == "✂️ 只保留中间区域(删除两边)":
                                # 只保留中间部分
                                crop_command = [
                                    'ffmpeg', '-i', input_path,
                                    '-ss', str(crop_start),
                                    '-to', str(crop_end),
                                    '-y', f"temp_cropped_{audio_file.name}"
                                ]
                            else:
                                # 删除中间,拼接两边:使用concat滤镜
                                # 先获取总时长
                                duration_info, _, _, _ = get_audio_info(input_path)
                                if duration_info:
                                    total_duration = duration_info
                                    # 构建concat命令: [0:a]atrim=0:start + [0:a]atrim=end:duration
                                    crop_command = [
                                        'ffmpeg', '-i', input_path,
                                        '-filter_complex',
                                        f'[0:a]atrim=0:{crop_start}[a1];[0:a]atrim={crop_end}:{total_duration}[a2];[a1][a2]concat=n=2:v=0:a=1[out]',
                                        '-map', '[out]',
                                        '-y', f"temp_cropped_{audio_file.name}"
                                    ]
                                else:
                                    st.error(f"❌ 无法获取 {audio_file.name} 的时长信息")
                                    failed_files.append((audio_file.name, "无法获取音频时长"))
                                    continue
                            
                            subprocess.run(crop_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            input_path = f"temp_cropped_{audio_file.name}"
                    
                    # 转换音频
                    if audio_file.name.endswith('.pcm'):
                        # PCM文件处理逻辑
                        sr = pcm_params.get('sample_rate', 16000)
                        ch = pcm_params.get('channels', 1)
                        
                        if output_format == 'PCM':
                            # PCM转PCM:只需修改采样率/声道数
                            # 先用Python的wave模块添加WAV头,再用ffmpeg转换
                            wav_path = f"temp_intermediate.wav"
                            with wave.open(wav_path, 'wb') as wf:
                                wf.setnchannels(ch)
                                wf.setsampwidth(2)
                                wf.setframerate(sr)
                                with open(input_path, 'rb') as pf:
                                    wf.writeframes(pf.read())
                            
                            # 然后用ffmpeg转换采样率/声道数
                            convert_audio(wav_path, output_path, 'pcm', output_sr, output_channels)
                            if os.path.exists(wav_path):
                                os.remove(wav_path)
                        else:
                            # PCM转其他格式(WAV/MP3/M4A)
                            # 先用Python的wave模块添加WAV头
                            wav_path = f"temp_intermediate.wav"
                            with wave.open(wav_path, 'wb') as wf:
                                wf.setnchannels(ch)
                                wf.setsampwidth(2)
                                wf.setframerate(sr)
                                with open(input_path, 'rb') as pf:
                                    wf.writeframes(pf.read())
                            
                            # 然后用ffmpeg转换为目标格式
                            convert_audio(wav_path, output_path, output_format.lower(), output_sr, output_channels)
                            if os.path.exists(wav_path):
                                os.remove(wav_path)
                    else:
                        # 非PCM文件直接转换
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
