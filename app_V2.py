import streamlit as st
import os
from io import BytesIO
import subprocess
import wave
import zipfile
import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile

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
    ["🎵 M4A → WAV", " WAV → PCM", "💿 PCM → WAV", "📉 48K → 16K", "✂️ PCM 裁剪器(含播放)"],
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

# ==================== 工具 5: PCM 裁剪器(含播放) ====================

elif audio_tool == "✂️ PCM 裁剪器(含播放)":
    st.header("✂️ PCM 音频裁剪器 & 播放器")
    st.info("上传 PCM 文件后可直接播放试听,并通过可视化选择要删除的区域")
    
    col1, col2 = st.columns(2)
    with col1:
        sample_rate = st.number_input("采样率 (Hz)", value=16000, step=1000, key="sample_rate_cutter")
    with col2:
        channels = st.number_input("声道数", value=1, min_value=1, max_value=2, key="channels_cutter")
    
    pcm_file = st.file_uploader(
        "上传 PCM 文件",
        type=["pcm"],
        key="pcm_upload_cutter"
    )
    
    if pcm_file:
        st.success(f"✅ 已选择文件: {pcm_file.name}")
        
        # 读取 PCM 数据
        pcm_data = pcm_file.read()
        pcm_array = np.frombuffer(pcm_data, dtype=np.int16)
        duration = len(pcm_array) / sample_rate
        
        st.info(f" 音频时长: {duration:.2f} 秒")
        st.caption(" 提示:波形图横坐标即为时间(秒),手动输入的时间应对应图中的坐标值")
        
        # 播放功能
        st.subheader("🎧 播放音频")
        if st.button("▶️ 播放完整音频", type="primary", key="play_pcm_in_cutter"):
            try:
                # 转换为 WAV 格式以便播放
                wav_buffer = BytesIO()
                with wave.open(wav_buffer, 'wb') as wf:
                    wf.setnchannels(channels)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(pcm_data)
                
                wav_buffer.seek(0)
                st.audio(wav_buffer, format="audio/wav")
                st.success(" 音频已加载,点击播放按钮即可试听")
            except Exception as e:
                st.error(f" 播放失败: {str(e)}")
        
        st.divider()
        
        # 绘制频谱图
        st.subheader("🎨 音频频谱图")
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={'height_ratios': [3, 1]})
        
        # 上图:频谱图
        audio_data = pcm_array.astype(float)
        if channels == 2:
            audio_data = audio_data.reshape(-1, 2)[:, 0]  # 取左声道
        
        # 使用 scipy 计算频谱图
        from scipy.signal import spectrogram as scipy_spectrogram
        f, t, Sxx = scipy_spectrogram(audio_data, fs=sample_rate, nperseg=256, noverlap=128)
        
        # 绘制频谱图
        im = ax1.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud', cmap='viridis')
        ax1.set_ylabel('频率 (Hz)', fontsize=12)
        ax1.set_title('频谱图 - 拖动滑块选择裁剪区域', fontsize=14)
        fig.colorbar(im, ax=ax1, label='功率 (dB)')
        
        # 下图:波形图
        time_axis = np.arange(len(pcm_array)) / sample_rate
        ax2.plot(time_axis, pcm_array, linewidth=0.5, color='#1f77b4')
        ax2.set_xlabel('时间 (秒)', fontsize=12)
        ax2.set_ylabel('振幅', fontsize=12)
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
        
        # 裁剪控制 - 交互式选择
        st.subheader("️ 裁剪设置")
                
        # 选择裁剪模式
        cut_mode = st.radio(
            "选择裁剪模式:",
            ["🗑️ 删除中间区域(保留两边)", "✂️ 只保留中间区域(删除两边)"],
            horizontal=True,
            key="cut_mode_radio"
        )
                
        if cut_mode == "🗑️ 删除中间区域(保留两边)":
            st.info(" 在波形图上点击两个位置来选择要**删除**的区域:")
            st.markdown("- **第1次点击**: 设置删除区域起点")
            st.markdown("- **第2次点击**: 设置删除区域终点")
            st.markdown("- 中间区域将被删除,两侧音频会自动拼接")
        else:
            st.info("💡 在波形图上点击两个位置来选择要**保留**的区域:")
            st.markdown("- **第1次点击**: 设置保留区域起点")
            st.markdown("- **第2次点击**: 设置保留区域终点")
            st.markdown("- 只保留中间区域,两侧音频将被删除")
        
        # 初始化 session state
        if 'click_count' not in st.session_state:
            st.session_state.click_count = 0
        if 'click_points' not in st.session_state:
            st.session_state.click_points = []
        
        # 重置按钮
        col_reset, col_info = st.columns([1, 3])
        with col_reset:
            if st.button("🔄 重置选择", key="reset_selection"):
                st.session_state.click_count = 0
                st.session_state.click_points = []
                st.rerun()
        
        with col_info:
            if cut_mode == "🗑️ 删除中间区域(保留两边)":
                # 删除模式
                if st.session_state.click_count == 0:
                    st.info("⏳ 请在波形图区域点击选择删除起点")
                elif st.session_state.click_count == 1:
                    st.info(f"✅ 已选择起点: {st.session_state.click_points[0]:.2f}秒 | 请点击选择终点")
                else:
                    start_del = st.session_state.click_points[0]
                    end_del = st.session_state.click_points[1]
                    if start_del > end_del:
                        start_del, end_del = end_del, start_del
                    
                    # 计算保留区域
                    keep_start_to_start = start_del
                    keep_end_to_end = duration - end_del
                    
                    st.success(f"✅ 将删除: {start_del:.2f}s - {end_del:.2f}s (删除时长: {end_del - start_del:.2f}s)")
                    st.info(f"📊 保留: 0-{start_del:.2f}s + {end_del:.2f}s-{duration:.2f}s (总时长: {keep_start_to_start + keep_end_to_end:.2f}s)")
            else:
                # 保留模式
                if st.session_state.click_count == 0:
                    st.info("⏳ 请在波形图区域点击选择保留起点")
                elif st.session_state.click_count == 1:
                    st.info(f"✅ 已选择起点: {st.session_state.click_points[0]:.2f}秒 | 请点击选择终点")
                else:
                    start_keep = st.session_state.click_points[0]
                    end_keep = st.session_state.click_points[1]
                    if start_keep > end_keep:
                        start_keep, end_keep = end_keep, start_keep
                    
                    # 计算删除区域
                    delete_start_to_start = start_keep
                    delete_end_to_end = duration - end_keep
                    
                    st.success(f"✅ 将保留: {start_keep:.2f}s - {end_keep:.2f}s (保留时长: {end_keep - start_keep:.2f}s)")
                    st.info(f" 删除: 0-{start_keep:.2f}s + {end_keep:.2f}s-{duration:.2f}s (总删除时长: {delete_start_to_start + delete_end_to_end:.2f}s)")
        
        # 显示交互式波形图(带点击功能)
        st.subheader("📊 波形图 - 点击选择删除区域")
        
        # 创建可点击的波形图
        fig, ax = plt.subplots(figsize=(14, 4))
        time_axis = np.arange(len(pcm_array)) / sample_rate
        ax.plot(time_axis, pcm_array, linewidth=0.5, color='#1f77b4')
        ax.set_xlabel('时间 (秒)', fontsize=12)
        ax.set_ylabel('振幅', fontsize=12)
        ax.set_title('点击波形图选择要删除的区域', fontsize=14)
        ax.grid(True, alpha=0.3)
        
        # 如果已经选择了点,绘制标记
        if len(st.session_state.click_points) >= 1:
            point1 = st.session_state.click_points[0]
            if cut_mode == "🗑️ 删除中间区域(保留两边)":
                ax.axvline(x=point1, color='red', linestyle='--', linewidth=2, label=f'删除起点: {point1:.2f}s')
            else:
                ax.axvline(x=point1, color='green', linestyle='--', linewidth=2, label=f'保留起点: {point1:.2f}s')
        
        if len(st.session_state.click_points) >= 2:
            point1 = min(st.session_state.click_points)
            point2 = max(st.session_state.click_points)
            if cut_mode == "🗑️ 删除中间区域(保留两边)":
                ax.axvline(x=point2, color='orange', linestyle='--', linewidth=2, label=f'删除终点: {point2:.2f}s')
                # 高亮要删除的区域
                ax.axvspan(point1, point2, alpha=0.3, color='red', label='将删除此区域')
            else:
                ax.axvline(x=point2, color='lightgreen', linestyle='--', linewidth=2, label=f'保留终点: {point2:.2f}s')
                # 高亮要保留的区域
                ax.axvspan(point1, point2, alpha=0.3, color='green', label='将保留此区域')
            ax.legend(loc='upper right')
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
        
        # JavaScript 点击交互(使用 streamlit 的组件)
        import streamlit.components.v1 as components
        
        click_js = """
        <script>
        const plotContainer = document.querySelector('[data-testid="stMetric"]');
        if (plotContainer) {
            plotContainer.addEventListener('click', function(e) {
                const rect = e.target.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const width = rect.width;
                // 这里需要映射到实际时间,简化处理
                console.log('Clicked at:', x, width);
            });
        }
        </script>
        """
        
        # 由于 Streamlit 不支持直接的图形点击,我们使用时间输入作为备选
        st.divider()
        st.subheader(" 精确时间输入(可选)")
        st.caption("如果上面的点击方式不够精确,可以手动输入时间")
                
        col1, col2 = st.columns(2)
        with col1:
            if cut_mode == "🗑️ 删除中间区域(保留两边)":
                label1 = "删除起点 (秒)"
            else:
                label1 = "保留起点 (秒)"
                    
            delete_start = st.number_input(
                label1,
                min_value=0.0,
                max_value=duration,
                value=st.session_state.click_points[0] if len(st.session_state.click_points) > 0 else 0.0,
                step=0.01,
                format="%.2f",
                key="delete_start_input"
            )
        with col2:
            if cut_mode == "🗑️ 删除中间区域(保留两边)":
                label2 = "删除终点 (秒)"
            else:
                label2 = "保留终点 (秒)"
                    
            delete_end = st.number_input(
                label2,
                min_value=0.0,
                max_value=duration,
                value=st.session_state.click_points[1] if len(st.session_state.click_points) > 1 else duration,
                step=0.01,
                format="%.2f",
                key="delete_end_input"
            )
        
        # 验证并执行裁剪
        if delete_start >= delete_end:
            st.warning("⚠️ 起点必须小于终点")
        else:
            if cut_mode == "🗑️ 删除中间区域(保留两边)":
                st.success(f"✅ 将删除区间: {delete_start:.2f}s - {delete_end:.2f}s")
                button_label = "🗑️ 执行删除并拼接"
            else:
                st.success(f"✅ 将保留区间: {delete_start:.2f}s - {delete_end:.2f}s")
                button_label = "✂️ 执行裁剪,只保留此段"
            
            # 显示调试信息
            with st.expander(" 查看时间对应关系(调试信息)"):
                st.write(f"📊 **音频信息**:")
                st.write(f"- 采样率: {sample_rate} Hz")
                st.write(f"- 声道数: {channels}")
                st.write(f"- 总时长: {duration:.2f} 秒")
                st.write(f"- 总采样点数: {len(pcm_array)}")
                st.write(f"")
                st.write(f"️ **裁剪设置**:")
                st.write(f"- 起点: {delete_start:.2f}秒 → 采样点索引: {int(delete_start * sample_rate)} → 字节索引: {int(delete_start * sample_rate) * 2 * channels}")
                st.write(f"- 终点: {delete_end:.2f}秒 → 采样点索引: {int(delete_end * sample_rate)} → 字节索引: {int(delete_end * sample_rate) * 2 * channels}")
                st.write(f"- 💡 波形图坐标: 横轴就是时间(秒),输入5.00就对应图中的5秒位置")
            
            if st.button(button_label, type="primary", key="execute_cut"):
                try:
                    # 计算采样点(注意:pcm_array是int16数组,每个元素就是一个采样点)
                    # 时间(秒) * 采样率 = 采样点索引
                    start_sample_index = int(delete_start * sample_rate)
                    end_sample_index = int(delete_end * sample_rate)
                    
                    # 转换为字节索引(每个采样点2字节,channels声道)
                    start_byte = start_sample_index * 2 * channels
                    end_byte = end_sample_index * 2 * channels
                    
                    # 确保字节索引对齐(2字节=16bit)
                    start_byte = start_byte - (start_byte % 2)
                    end_byte = end_byte - (end_byte % 2)
                    
                    # 调试信息
                    st.info(f" 调试: 时间{delete_start:.2f}s→{delete_end:.2f}s | 采样点{start_sample_index}→{end_sample_index} | 字节{start_byte}→{end_byte}")
                    
                    if cut_mode == "🗑️ 删除中间区域(保留两边)":
                        # 删除模式:提取保留的部分 - 前面部分 + 后面部分
                        before_delete = pcm_data[:start_byte]
                        after_delete = pcm_data[end_byte:]
                        result_pcm = before_delete + after_delete
                    else:
                        # 保留模式:只提取中间部分
                        result_pcm = pcm_data[start_byte:end_byte]
                    
                    # 转换为 WAV 格式
                    wav_buffer = BytesIO()
                    with wave.open(wav_buffer, 'wb') as wf:
                        wf.setnchannels(channels)
                        wf.setsampwidth(2)
                        wf.setframerate(sample_rate)
                        wf.writeframes(result_pcm)
                    
                    wav_buffer.seek(0)
                    
                    # 计算新时长
                    new_duration = len(result_pcm) / (sample_rate * channels * 2)
                    
                    # 显示结果
                    st.subheader("🎧 处理后的音频")
                    st.audio(wav_buffer, format="audio/wav")
                    
                    if cut_mode == "️ 删除中间区域(保留两边)":
                        st.info(f"📊 新音频时长: {new_duration:.2f}秒 (删除了 {delete_end - delete_start:.2f}秒)")
                    else:
                        st.info(f"📊 新音频时长: {new_duration:.2f}秒 (保留了 {delete_end - delete_start:.2f}秒)")
                    
                    # 提供下载
                    if cut_mode == "🗑️ 删除中间区域(保留两边)":
                        output_filename = f"deleted_{os.path.splitext(pcm_file.name)[0]}.wav"
                    else:
                        output_filename = f"kept_{os.path.splitext(pcm_file.name)[0]}.wav"
                    
                    st.download_button(
                        label="📥 下载结果 (WAV)",
                        data=wav_buffer.getvalue(),
                        file_name=output_filename,
                        mime="audio/wav",
                        key="download_result_pcm"
                    )
                    
                    if cut_mode == "🗑️ 删除中间区域(保留两边)":
                        st.success("✅ 删除完成!中间区域已移除,两侧音频已拼接")
                    else:
                        st.success("✅ 裁剪完成!只保留了选中的中间区域")
                    
                except Exception as e:
                    st.error(f"❌ 操作失败: {str(e)}")

# ==================== 底部信息 ====================

st.markdown("---")
st.caption("🎵 音频工具箱 | 支持 M4A/WAV/PCM 格式互转、采样率转换、PCM 播放与裁剪")




