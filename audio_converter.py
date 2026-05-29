import streamlit as st
import os
from io import BytesIO
import subprocess
import wave
import zipfile
import numpy as np
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
    """使用ffmpeg转换音频(优化性能版)"""
    codec_map = {
        'wav': 'pcm_s16le',
        'pcm': 'pcm_s16le',
        'mp3': 'libmp3lame',
        'm4a': 'aac'
    }
    
    codec = codec_map.get(target_format, 'pcm_s16le')
    
    command = ['ffmpeg', '-i', input_path]
    
    # 性能优化:使用多线程加速
    command.extend(['-threads', '0'])  # 0表示自动使用所有CPU核心
    
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
    
    try:
        # 性能优化:不捕获输出,直接输出到控制台,减少内存开销
        result = subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        # 输出详细的错误信息
        error_msg = f"FFmpeg命令失败:\n命令: {' '.join(command)}"
        raise RuntimeError(error_msg) from e

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

def generate_silence(duration, sample_rate=16000, channels=1):
    """生成静默音频数据(PCM格式)
    
    Args:
        duration: 静默时长(秒)
        sample_rate: 采样率
        channels: 声道数
    
    Returns:
        bytes: 静默音频数据
    """
    # 计算采样点数
    num_samples = int(duration * sample_rate)
    # 生成16位静音数据(全部为0)
    silence = np.zeros(num_samples * channels, dtype=np.int16)
    return silence.tobytes()

def adjust_volume(input_path, output_path, volume_db=0):
    """调整音频音量
    
    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径
        volume_db: 音量调整值(dB),正数增大,负数减小
    """
    command = [
        'ffmpeg', '-i', input_path,
        '-filter:a', f'volume={volume_db}dB',
        '-y', output_path
    ]
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def normalize_audio(input_path, output_path, target_db=-3.0):
    """音频标准化(归一化)
    
    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径
        target_db: 目标响度(dB),默认-3dB
    """
    command = [
        'ffmpeg', '-i', input_path,
        '-filter:a', f'loudnorm=I={target_db}:TP=-1.5:LRA=11',
        '-y', output_path
    ]
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def split_audio(input_path, output_dir, segment_duration, output_format='wav', sr=16000, channels=1):
    """将音频分割成多个小段(按固定时长)
    
    Args:
        input_path: 输入文件路径
        output_dir: 输出目录
        segment_duration: 每段时长(秒)
        output_format: 输出格式
        sr: 采样率(PCM格式需要)
        channels: 声道数(PCM格式需要)
    
    Returns:
        list: 分割后的文件路径列表
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取音频时长
    duration, audio_sr, audio_ch, codec = get_audio_info(input_path)
    if not duration:
        raise RuntimeError("无法获取音频时长")
    
    # 计算需要分割的段数
    num_segments = int(np.ceil(duration / segment_duration))
    
    output_files = []
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    
    for i in range(num_segments):
        start_time = i * segment_duration
        output_file = os.path.join(output_dir, f"{base_name}_part{i+1:03d}.{output_format}")
        
        # PCM格式需要特殊处理
        if output_format == 'pcm':
            command = [
                'ffmpeg', '-i', input_path,
                '-ss', str(start_time),
                '-t', str(segment_duration),
                '-f', 's16le', '-acodec', 'pcm_s16le',
                '-ar', str(sr), '-ac', str(channels),
                '-y', output_file
            ]
        else:
            command = [
                'ffmpeg', '-i', input_path,
                '-ss', str(start_time),
                '-t', str(segment_duration),
                '-y', output_file
            ]
        
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output_files.append(output_file)
    
    return output_files

def split_audio_by_silence(input_path, output_dir, silence_threshold=-50, min_silence_duration=0.5, output_format='wav', sr=16000, channels=1):
    """基于静音检测的智能音频分割
    
    Args:
        input_path: 输入文件路径
        output_dir: 输出目录
        silence_threshold: 静音阈值(dB),低于此值认为是静音,默认-50dB
        min_silence_duration: 最小静音持续时间(秒),超过此时长才认为是有意义的停顿,默认0.5秒
        output_format: 输出格式
        sr: 采样率(PCM格式需要)
        channels: 声道数(PCM格式需要)
    
    Returns:
        list: 分割后的文件路径列表
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 使用ffmpeg的silencedetect滤镜检测静音
    command = [
        'ffmpeg', '-i', input_path,
        '-af', f'silencedetect=noise={silence_threshold}dB:d={min_silence_duration}',
        '-f', 'null', '-'
    ]
    
    result = subprocess.run(command, capture_output=True, text=True)
    output = result.stderr
    
    # 解析静音检测结果
    import re
    silence_starts = []
    silence_ends = []
    
    for line in output.split('\n'):
        if 'silence_start:' in line:
            match = re.search(r'silence_start:\s*([\d.]+)', line)
            if match:
                silence_starts.append(float(match.group(1)))
        elif 'silence_end:' in line:
            match = re.search(r'silence_end:\s*([\d.]+)', line)
            if match:
                silence_ends.append(float(match.group(1)))
    
    # 获取音频总时长
    duration, audio_sr, audio_ch, codec = get_audio_info(input_path)
    if not duration:
        raise RuntimeError("无法获取音频时长")
    
    # 构建分割区间(非静音部分)
    segments = []
    
    if not silence_starts:
        # 没有检测到静音,整个音频作为一段
        segments.append((0, duration))
    else:
        # 第一个非静音段(从开始到第一个静音前)
        if silence_starts[0] > 0:
            segments.append((0, silence_starts[0]))
        
        # 中间的非静音段(静音结束后到下一个静音开始前)
        for i in range(len(silence_ends)):
            if i < len(silence_starts) - 1:
                start = silence_ends[i]
                end = silence_starts[i + 1]
                if end > start:
                    segments.append((start, end))
        
        # 最后一个非静音段(最后一个静音结束后到结束)
        if silence_ends:
            last_end = silence_ends[-1]
            if last_end < duration:
                segments.append((last_end, duration))
    
    # 执行分割
    output_files = []
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    
    for idx, (start, end) in enumerate(segments):
        output_file = os.path.join(output_dir, f"{base_name}_segment{idx+1:03d}.{output_format}")
        
        # PCM格式需要特殊处理
        if output_format == 'pcm':
            command = [
                'ffmpeg', '-i', input_path,
                '-ss', str(start),
                '-to', str(end),
                '-f', 's16le', '-acodec', 'pcm_s16le',
                '-ar', str(sr), '-ac', str(channels),
                '-y', output_file
            ]
        else:
            command = [
                'ffmpeg', '-i', input_path,
                '-ss', str(start),
                '-to', str(end),
                '-y', output_file
            ]
        
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output_files.append(output_file)
    
    return output_files

def convert_single_file(audio_file, idx, output_format, output_sr, output_channels, 
                        enable_crop, cut_mode, crop_start, crop_end, pcm_params,
                        enable_silence=False, silence_start=0.0, silence_end=0.0,
                        enable_volume=False, volume_mode='adjust', volume_value=0,
                        enable_split=False, split_duration=10.0):
    """单个文件转换函数(用于并行处理)"""
    input_path = f"temp_input_{idx}_{audio_file.name}"
    output_ext = output_format.lower()
    base_name = os.path.splitext(audio_file.name)[0]
    output_path = f"temp_output_{idx}_{base_name}.{output_ext}"
    
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
                        raise RuntimeError("无法获取音频时长")
                
                subprocess.run(crop_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                input_path = f"temp_cropped_{audio_file.name}"
        
        # 如果需要添加静默,使用ffmpeg的concat滤镜
        if enable_silence and (silence_start > 0 or silence_end > 0):
            temp_silence_start = f"temp_silence_start_{idx}.wav"
            temp_silence_end = f"temp_silence_end_{idx}.wav"
            temp_with_silence = f"temp_with_silence_{idx}.wav"
            
            try:
                # 获取当前音频信息
                if audio_file.name.endswith('.pcm'):
                    sr = pcm_params.get('sample_rate', 16000)
                    ch = pcm_params.get('channels', 1)
                else:
                    _, sr, ch, _ = get_audio_info(input_path)
                    if not sr:
                        sr = 16000
                    if not ch:
                        ch = 1
                
                parts = []
                
                # 添加开头静默
                if silence_start > 0:
                    silence_data = generate_silence(silence_start, sr, ch)
                    with wave.open(temp_silence_start, 'wb') as wf:
                        wf.setnchannels(ch)
                        wf.setsampwidth(2)
                        wf.setframerate(sr)
                        wf.writeframes(silence_data)
                    parts.append(temp_silence_start)
                
                # 添加原音频
                parts.append(input_path)
                
                # 添加结尾静默
                if silence_end > 0:
                    silence_data = generate_silence(silence_end, sr, ch)
                    with wave.open(temp_silence_end, 'wb') as wf:
                        wf.setnchannels(ch)
                        wf.setsampwidth(2)
                        wf.setframerate(sr)
                        wf.writeframes(silence_data)
                    parts.append(temp_silence_end)
                
                # 使用ffmpeg concat所有部分
                if len(parts) == 1:
                    # 只有原音频,不需要concat
                    temp_with_silence = input_path
                else:
                    # 构建concat命令
                    concat_inputs = ''
                    concat_filter = ''
                    for i, part in enumerate(parts):
                        concat_inputs += f'-i "{part}" '
                        concat_filter += f'[{i}:a]'
                    concat_filter += f'concat=n={len(parts)}:v=0:a=1[out]'
                    
                    concat_command = f'ffmpeg {concat_inputs} -filter_complex "{concat_filter}" -map "[out]" -y "{temp_with_silence}"'
                    subprocess.run(concat_command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # 更新input_path
                input_path = temp_with_silence
                
            except Exception as e:
                # 如果添加静默失败,继续使用原音频
                print(f"警告: 添加静默失败,将使用原音频: {str(e)}")
            finally:
                # 清理静默临时文件
                for tmp in [temp_silence_start, temp_silence_end]:
                    if os.path.exists(tmp):
                        try:
                            os.remove(tmp)
                        except:
                            pass
        
        # 音量调整/标准化
        if enable_volume:
            temp_volume = f"temp_volume_{idx}.wav"
            try:
                if volume_mode == 'normalize':
                    # 标准化到目标响度
                    normalize_audio(input_path, temp_volume, target_db=volume_value)
                else:
                    # 手动调整音量
                    adjust_volume(input_path, temp_volume, volume_db=volume_value)
                input_path = temp_volume
            except Exception as e:
                print(f"警告: 音量调整失败,将使用原音频: {str(e)}")
            finally:
                if os.path.exists(temp_volume):
                    # 如果已经更新了input_path,就不删除
                    if input_path != temp_volume:
                        try:
                            os.remove(temp_volume)
                        except:
                            pass
        
        # 转换音频
        if audio_file.name.endswith('.pcm'):
            # PCM文件处理逻辑
            sr = pcm_params.get('sample_rate', 16000)
            ch = pcm_params.get('channels', 1)
            
            # 性能优化:如果不需要转换,直接复制文件
            if output_format == 'PCM' and output_sr == sr and output_channels == ch and not enable_crop and not enable_silence:
                import shutil
                shutil.copy2(input_path, output_path)
            elif output_format == 'PCM':
                # PCM转PCM:只需修改采样率/声道数
                # 先用Python的wave模块添加WAV头,再用ffmpeg转换
                wav_path = f"temp_intermediate_{idx}.wav"
                try:
                    with wave.open(wav_path, 'wb') as wf:
                        wf.setnchannels(ch)
                        wf.setsampwidth(2)
                        wf.setframerate(sr)
                        with open(input_path, 'rb') as pf:
                            wf.writeframes(pf.read())
                    
                    # 然后用ffmpeg转换采样率/声道数
                    convert_audio(wav_path, output_path, 'pcm', output_sr, output_channels)
                except Exception as e:
                    # 如果ffmpeg失败,尝试直接使用Python处理
                    if output_sr == sr and output_channels == ch:
                        # 不需要转换,直接使用裁剪后的文件
                        import shutil
                        shutil.copy2(input_path, output_path)
                    else:
                        raise e
                finally:
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
            else:
                # PCM转其他格式(WAV/MP3/M4A)
                # 先用Python的wave模块添加WAV头
                wav_path = f"temp_intermediate_{idx}.wav"
                try:
                    with wave.open(wav_path, 'wb') as wf:
                        wf.setnchannels(ch)
                        wf.setsampwidth(2)
                        wf.setframerate(sr)
                        with open(input_path, 'rb') as pf:
                            wf.writeframes(pf.read())
                    
                    # 然后用ffmpeg转换为目标格式
                    convert_audio(wav_path, output_path, output_format.lower(), output_sr, output_channels)
                except Exception as e:
                    raise e
                finally:
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
        else:
            # 非PCM文件直接转换
            convert_audio(input_path, output_path, output_format.lower(), output_sr, output_channels)
        
        # 读取输出文件
        with open(output_path, 'rb') as f:
            output_data = f.read()
        
        output_filename = f"{base_name}_converted.{output_ext}"
        return ('success', output_filename, output_data, None)
        
    except Exception as e:
        return ('failed', audio_file.name, None, str(e))
    
    finally:
        # 清理临时文件
        for tmp in [input_path, output_path, f"temp_cropped_{idx}_{audio_file.name}", f"temp_intermediate_{idx}.wav", 
                    f"temp_with_silence_{idx}.wav", f"temp_silence_start_{idx}.wav", f"temp_silence_end_{idx}.wav"]:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except:
                    pass

# ==================== 3. 主页面布局 ====================

st.title("🎵 音频处理工具箱 Pro")
st.markdown("---")

# 性能优化配置
MAX_WORKERS = min(4, os.cpu_count() or 2)  # 最大并行线程数

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
    
    # 静默设置
    st.subheader(" 添加静默时间 (可选)")
    enable_silence = st.checkbox("在音频前后添加静默", key="enable_silence")
    
    if enable_silence:
        st.info(" 在音频的开头和/或结尾添加静音段，常用于制作音频样本、测试音频等")
        
        col1, col2 = st.columns(2)
        with col1:
            silence_start = st.number_input(
                "开头静默时长 (秒)",
                min_value=0.0,
                max_value=10.0,
                value=0.0,
                step=0.1,
                format="%.1f",
                key="silence_start"
            )
        with col2:
            silence_end = st.number_input(
                "结尾静默时长 (秒)",
                min_value=0.0,
                max_value=10.0,
                value=0.0,
                step=0.1,
                format="%.1f",
                key="silence_end"
            )
        
        if silence_start == 0 and silence_end == 0:
            st.warning("⚠️ 请设置开头或结尾的静默时长")
        else:
            if silence_start > 0:
                st.success(f"✅ 将在开头添加 {silence_start:.1f}秒 静默")
            if silence_end > 0:
                st.success(f"✅ 将在结尾添加 {silence_end:.1f}秒 静默")
    
    st.divider()
    
    # 音量设置
    st.subheader(" 音量调整 (可选)")
    enable_volume = st.checkbox("启用音量调整", key="enable_volume")
    
    if enable_volume:
        volume_mode = st.radio(
            "选择音量调整模式:",
            [" 手动调整", "📊 标准化(归一化)"],
            horizontal=True,
            key="volume_mode"
        )
        
        if volume_mode == " 手动调整":
            st.info(" 手动设置音量增益,正数增大音量,负数减小音量")
            volume_value = st.slider(
                "音量调整 (dB)",
                min_value=-20.0,
                max_value=20.0,
                value=0.0,
                step=0.5,
                format="%.1f",
                key="volume_slider"
            )
            if volume_value > 0:
                st.success(f"✅ 将增大音量 {volume_value:.1f}dB")
            elif volume_value < 0:
                st.info(f" 将减小音量 {abs(volume_value):.1f}dB")
            else:
                st.warning("⚠️ 音量调整为0dB,不会改变音量")
        else:
            st.info(" 自动调整音量到目标响度,使所有音频音量一致")
            volume_value = st.selectbox(
                "目标响度 (dB)",
                [-23.0, -16.0, -10.0, -3.0],
                index=3,
                key="normalize_db"
            )
            st.success(f"✅ 将标准化到 {volume_value:.1f}dB LUFS")
    
    st.divider()
    
    # 音频分割设置
    st.subheader(" 音频分割 (可选)")
    enable_split = st.checkbox("启用音频分割", key="enable_split")
            
    if enable_split:
        # 选择分割模式
        split_mode = st.radio(
            "选择分割模式:",
            [" 按固定时长分割", " 智能分割(基于静音检测)"],
            horizontal=True,
            key="split_mode_radio"
        )
                
        if split_mode == " 按固定时长分割":
            st.info(" 将每个音频文件按指定时长平均分割成多个小段")
                    
            col1, col2 = st.columns(2)
            with col1:
                split_duration = st.number_input(
                    "每段时长 (秒)",
                    min_value=1.0,
                    max_value=3600.0,
                    value=10.0,
                    step=1.0,
                    format="%.1f",
                    key="split_duration"
                )
                    
            st.success(f" 每 {split_duration:.1f}秒 分割一次")
            st.info(" 分割格式将自动使用上方设置的输出格式: **{output_format}**")
                    
        else:  # 智能分割
            st.info(" 自动识别音频中的静音/停顿,将内容按自然分段切割,适合语音、播客、会议录音等")
                    
            col1, col2 = st.columns(2)
            with col1:
                silence_threshold = st.slider(
                    "静音阈值 (dB)",
                    min_value=-80.0,
                    max_value=-20.0,
                    value=-50.0,
                    step=1.0,
                    format="%.1f",
                    key="silence_threshold",
                    help="低于此值的音量被认为是静音。值越小(如-60dB)越严格,值越大(如-40dB)越宽松"
                )
            with col2:
                min_silence_duration = st.number_input(
                    "最小静音时长 (秒)",
                    min_value=0.1,
                    max_value=5.0,
                    value=0.5,
                    step=0.1,
                    format="%.1f",
                    key="min_silence_duration",
                    help="静音持续时间超过此值才认为是有效的分段点"
                )
                    
            st.success(f" 阈值: {silence_threshold:.1f}dB, 最小静音: {min_silence_duration:.1f}秒")
            st.caption("💡 提示: 语音通常使用 -50dB/0.5秒,音乐使用 -60dB/0.3秒")
            st.info(" 分割格式将自动使用上方设置的输出格式: **{output_format}**")
                
        if len(uploaded_files) > 1:
            st.warning(f" 将对所有 {len(uploaded_files)} 个文件执行分割")
    
    st.divider()
    
    # 操作按钮
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        play_all = st.button("▶️ 播放全部音频", type="secondary", key="play_all")
    with col2:
        convert_all = st.button("🚀 转换并下载", type="primary", key="convert_all")
    with col3:
        if st.button(" 重置", key="reset_all"):
            st.rerun()
    
    # 确保所有变量都有默认值,避免未定义错误
    # 静默相关变量
    if not enable_silence:
        silence_start = 0.0
        silence_end = 0.0
    
    # 音量相关变量  
    if not enable_volume:
        volume_mode = 'adjust'
        volume_value = 0
    
    # 分割相关变量
    if not enable_split:
        split_mode = " 按固定时长分割"
        split_duration = 10.0
        silence_threshold = -50.0
        min_silence_duration = 0.5
    
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
            st.error(" 请先修正裁剪时间!")
        elif enable_silence and silence_start == 0 and silence_end == 0:
            st.error(" 请设置静默时长!")
        else:
            st.subheader("🔄 处理进度")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            converted_files = []
            failed_files = []
            total_files = len(uploaded_files)
            completed_count = 0
            lock = threading.Lock()
            
            # 性能优化:使用线程池并行处理
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # 提交所有任务
                future_to_idx = {
                    executor.submit(
                        convert_single_file, 
                        audio_file, idx, output_format, output_sr, output_channels,
                        enable_crop, cut_mode if enable_crop else None,
                        crop_start if enable_crop else 0, crop_end if enable_crop else 0,
                        pcm_params,
                        enable_silence, silence_start, silence_end,
                        enable_volume, volume_mode if enable_volume else 'adjust',
                        volume_value if enable_volume else 0,
                        False, 0  # split功能在转换后单独执行
                    ): idx for idx, audio_file in enumerate(uploaded_files)
                }
                
                # 处理完成的任务
                for future in as_completed(future_to_idx):
                    result = future.result()
                    status_type, filename_or_name, data_or_none, error = result
                    
                    with lock:
                        completed_count += 1
                        progress = completed_count / total_files
                        progress_bar.progress(progress)
                        
                        if status_type == 'success':
                            converted_files.append((filename_or_name, data_or_none))
                            status_text.text(f"✅ 已处理: {filename_or_name} ({completed_count}/{total_files})")
                        else:
                            failed_files.append((filename_or_name, error))
                            status_text.text(f"❌ 失败: {filename_or_name} ({completed_count}/{total_files})")
            
            progress_bar.empty()
            status_text.empty()
            
            # 根据输出格式确定文件扩展名
            format_ext_map = {
                'WAV': 'wav',
                'PCM': 'pcm',
                'MP3': 'mp3',
                'M4A': 'm4a'
            }
            output_ext = format_ext_map.get(output_format, 'wav')
            
            # 如果启用了分割,对每个转换后的文件执行分割
            if enable_split:
                st.subheader(" 正在分割音频...")
                split_progress = st.progress(0)
                split_status = st.empty()
                            
                all_split_files = []
                temp_split_dir = "temp_split_output"
                            
                for idx, (fname, fdata) in enumerate(converted_files):
                    split_status.text(f"正在分割: {fname} ({idx+1}/{len(converted_files)})")
                                
                    # 保存临时文件
                    temp_input = f"temp_split_input_{idx}.{output_ext}"
                    with open(temp_input, 'wb') as f:
                        f.write(fdata)
                                
                    try:
                        # 根据分割模式执行不同的分割函数
                        # 分割格式自动使用上方设置的output_format
                        split_format_lower = output_format.lower()
                        
                        if split_mode == " 智能分割(基于静音检测)":
                            # 智能分割:基于静音检测
                            split_files = split_audio_by_silence(
                                temp_input, temp_split_dir, 
                                silence_threshold, min_silence_duration, 
                                split_format_lower,
                                output_sr, output_channels  # 传递采样率和声道参数
                            )
                        else:
                            # 按固定时长分割
                            split_files = split_audio(
                                temp_input, temp_split_dir, 
                                split_duration, split_format_lower,
                                output_sr, output_channels  # 传递采样率和声道参数
                            )
                                    
                        # 读取分割后的文件
                        for split_file in split_files:
                            with open(split_file, 'rb') as f:
                                split_data = f.read()
                            split_name = os.path.basename(split_file)
                            
                            # 检查文件是否有效(时长>0.1秒)
                            try:
                                split_duration_check, _, _, _ = get_audio_info(split_file)
                                if split_duration_check and split_duration_check > 0.1:
                                    all_split_files.append((split_name, split_data))
                                else:
                                    print(f"跳过无效片段: {split_name} (时长: {split_duration_check}秒)")
                            except:
                                # 如果无法获取时长,保留文件
                                all_split_files.append((split_name, split_data))
                            
                            os.remove(split_file)  # 清理分割文件
                                    
                        # 删除临时目录(如果为空)
                        try:
                            os.rmdir(temp_split_dir)
                        except:
                            pass
                                    
                    except Exception as e:
                        st.error(f" 分割失败 {fname}: {str(e)}")
                    finally:
                        if os.path.exists(temp_input):
                            os.remove(temp_input)
                                
                    split_progress.progress((idx + 1) / len(converted_files))
                
                split_progress.empty()
                split_status.empty()
                
                # 使用分割后的文件
                if all_split_files:
                    converted_files = all_split_files
                    st.success(f"✅ 成功分割为 {len(converted_files)} 个文件")
                    
                    # 添加试听功能
                    st.subheader("🎧 试听分割结果")
                    st.info(" 点击播放按钮即可在线试听每个分割片段")
                    
                    # 创建可折叠的播放器列表
                    with st.expander(" 展开查看所有分割片段", expanded=True):
                        for idx, (fname, fdata) in enumerate(converted_files):
                            st.markdown(f"**片段 {idx+1}: {fname}**")
                            
                            # 确定MIME类型
                            if fname.endswith('.wav'):
                                mime_type = "audio/wav"
                            elif fname.endswith('.mp3'):
                                mime_type = "audio/mp3"
                            elif fname.endswith('.m4a'):
                                mime_type = "audio/mp4"
                            elif fname.endswith('.pcm'):
                                # PCM需要转换为WAV才能播放
                                try:
                                    sr = output_sr
                                    ch = output_channels
                                    fdata = pcm_to_wav_buffer(fdata, sr, ch)
                                    mime_type = "audio/wav"
                                except:
                                    st.warning("⚠️ PCM格式无法直接播放,请下载后使用专业工具播放")
                                    continue
                            else:
                                mime_type = "application/octet-stream"
                            
                            # 显示音频播放器
                            try:
                                st.audio(fdata, format=mime_type)
                            except Exception as e:
                                st.error(f"❌ 播放失败: {str(e)}")
                            
                            # 获取音频信息
                            try:
                                # 保存临时文件获取信息
                                temp_play_path = f"temp_play_{idx}.{fname.split('.')[-1]}"
                                with open(temp_play_path, 'wb') as f:
                                    f.write(fdata)
                                
                                if not fname.endswith('.pcm'):
                                    duration, sr, ch, codec = get_audio_info(temp_play_path)
                                    if duration:
                                        st.caption(f"⏱️ 时长: {duration:.2f}秒 |  采样率: {sr}Hz | 🔊 声道: {ch}")
                                
                                if os.path.exists(temp_play_path):
                                    os.remove(temp_play_path)
                            except:
                                pass
                            
                            st.markdown("---")
            
            # 显示结果
            if converted_files:
                st.success(f"✅ 最终生成 {len(converted_files)} 个文件")
                
                if len(converted_files) == 1:
                    fname, fdata = converted_files[0]
                    st.download_button(
                        label=f"📥 下载 {fname}",
                        data=fdata,
                        file_name=fname,
                        mime="audio/wav" if output_format == "WAV" else "application/octet-stream",
                        key="download_single"
                    )
                else:
                    # 多个文件打包ZIP - 性能优化:使用流式写入
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
                        for fname, fdata in converted_files:
                            zip_file.writestr(fname, fdata)
                    
                    download_label = " 下载全部结果 (ZIP)"
                    download_filename = f"converted_{output_format.lower()}_files.zip"
                    if enable_split:
                        download_filename = f"split_{output_format.lower()}_files.zip"
                    
                    st.download_button(
                        label=download_label,
                        data=zip_buffer.getvalue(),
                        file_name=download_filename,
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


