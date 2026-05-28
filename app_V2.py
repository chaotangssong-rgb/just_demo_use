import streamlit as st
import dashscope
from dashscope import Generation
import os
import json
from io import BytesIO
import httpx
from openai import OpenAI
import pandas as pd
import re
import subprocess
import shutil
import wave
from openpyxl.utils import get_column_letter
from openpyxl import Workbook
from openpyxl.styles import Font
import zipfile
import time

# ==================== 1. 配置与初始化 ====================

# 设置页面配置
st.set_page_config(
    page_title="AI 语音语料智能处理平台",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 默认的千问 API Key
DEFAULT_API_KEY = "sk-e10cbbca48ea4f23a590884e59b3d7c9"

# ==================== 2. 侧边栏 - API Key 配置 ====================

with st.sidebar:
    st.header("⚙️ 系统配置")

    # API Key 使用模式选择
    api_key_mode = st.radio(
        "🔑 API Key 模式",
        options=["默认 API Key", "自定义 API Key"],
        help="选择使用默认配置的 API Key 或自己输入",
        index=0
    )

    # 根据模式设置 API Key
    if api_key_mode == "默认 API Key":
        api_key = DEFAULT_API_KEY
        st.info("✅ 使用默认 API Key")
    else:
        api_key = st.text_input(
            "请输入您的千问 API Key",
            type="password",
            value=st.session_state.get('api_key', ''),
            help="请输入您的阿里云 DashScope API Key"
        )
        if api_key:
            st.session_state['api_key'] = api_key

    # 配置 http_client（用于 OpenAI SDK 访问）
    os.environ['NO_PROXY'] = '*'
    http_client = httpx.Client(verify=False, timeout=60.0, trust_env=False)

    # 创建 OpenAI 客户端（使用兼容模式访问千问）
    client_qwen = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        http_client=http_client
    )

    # 设置 dashscope 的 API Key（备用）
    if api_key:
        dashscope.api_key = api_key
        st.success("✅ API Key 已配置")
    else:
        st.warning("⚠️ 请先配置 API Key")

    st.divider()

    st.markdown("""
    ### 📖 使用说明
    1. **用例上传**: 上传 Excel 语料文件
    2. **AI 设计**: AI 生成新语料
    3. **批量标注**: 批量自动标注意图和槽位
    4. **报告分析**: 数据统计和可视化分析
    5. **工具箱**: Excel 清洗、音频转换等工具
    """)

# ==================== 3. 工具函数 ====================

def init_session_state():
    """初始化 session state，用于存储项目和语言选项"""
    if 'projects' not in st.session_state:
        st.session_state['projects'] = ['ZZ_NISSAN', 'DF_NISSAN', 'BYD', 'MaZda']
    if 'languages' not in st.session_state:
        st.session_state['languages'] = ['英语', '西班牙语', '阿拉伯语', '葡萄牙语', '瑞典语', '荷兰语', '意大利语',
                                         '法语', '挪威语', '波兰语']

# 初始化 session state
init_session_state()

def call_qwen_llm(system_prompt: str, user_prompt: str, model: str = "qwen-max"):
    """
    调用千问大模型（使用 OpenAI SDK）
    """
    if not api_key:
        return "❌ 错误：请先在侧边栏配置 API Key"

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = client_qwen.chat.completions.create(
            model=model,
            messages=messages
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"❌ 异常：{str(e)}"

def generate_unique_id(lang: str, text: str, index: int = None) -> str:
    """生成唯一 ID 用于去重"""
    import hashlib
    import time

    combined = f"{str(lang).strip().lower()}_{str(text).strip().lower()}"

    if index is not None:
        combined += f"_{index}_{time.time()}"

    return hashlib.md5(combined.encode('utf-8')).hexdigest()

# ==================== 4. 主页面布局 ====================

st.title("🚗 AI 语音语料智能处理平台")
st.markdown("---")

# 创建四个功能模块标签页
tab_upload, tab_design, tab_annotate, tab_analysis, tab_tools = st.tabs([
    "📤 用例上传",
    "✨ AI 设计",
    "🪄 批量标注",
    " 报告分析",
    "🛠️ 工具箱"
])

# ==================== Tab 1: 用例上传 ====================

with tab_upload:
    st.header("📤 用例上传")
    st.info("上传 Excel 格式的语料文件，支持查看和下载")

    # 上传 Excel 文件
    uploaded_file = st.file_uploader(
        "选择 Excel 文件 (.xlsx)",
        type=["xlsx"],
        help="Excel 文件应包含语料数据",
        key="upload_file"
    )

    if uploaded_file:
        try:
            # 读取 Excel 预览
            df_preview = pd.read_excel(uploaded_file)
            
            with st.expander(" 查看文件内容", expanded=True):
                st.dataframe(df_preview.head(10))
                st.write(f"✅ 成功读取 {len(df_preview)} 行数据")
                st.write(f" 列名：{list(df_preview.columns)}")

            st.divider()

            # 下载按钮
            st.subheader("💾 下载文件")
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_preview.to_excel(writer, index=False)

            st.download_button(
                label="📥 下载 Excel",
                data=output.getvalue(),
                file_name=f"processed_{uploaded_file.name}",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"❌ 文件读取失败：{str(e)}")
            import traceback
            st.code(traceback.format_exc())

# ==================== Tab 2: AI 设计 ====================

with tab_design:
    st.header("✨ AI 语料设计")
    st.info("使用 AI 直接生成新语料，无需向量库")

    # 基础配置
    st.subheader("1️⃣ 基础配置")
    col1, col2 = st.columns(2)

    with col1:
        selected_project = st.selectbox(
            "📁 项目名称",
            options=st.session_state.get('projects', ['默认项目']),
            index=0
        )

    with col2:
        selected_language = st.selectbox(
            "🌐 语言",
            options=st.session_state.get('languages', ['英语']),
            index=0
        )

    st.divider()

    # AI 生成指令
    st.subheader("2️⃣ AI 生成指令")
    
    natural_query = st.text_area(
        "请输入生成指令",
        placeholder="""示例：
- 设计 10 条西班牙语打开车窗的 case
- 生成 15 条德语查询天气的语料，包含不同城市
- 创建 20 条法语控制音乐播放的 case，要有音量调节
        """,
        height=150,
        key="design_query_input"
    )

    quantity = st.slider("生成数量", min_value=5, max_value=50, value=10, step=5)

    st.divider()

    # 执行按钮
    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        execute_btn = st.button("🚀 开始生成", type="primary", key="execute_design")
    with col_btn2:
        if st.button("🗑️ 清空结果", key="clear_design"):
            if 'generated_cases' in st.session_state:
                del st.session_state['generated_cases']
            st.rerun()

    if execute_btn and natural_query:
        with st.spinner("🤖 AI 正在生成语料..."):
            try:
                design_prompt = f"""你是一个车载语音语料设计专家。请生成符合以下要求的新语料。

【生成要求】:
- 主题：{natural_query}
- 目标语言：{selected_language}
- 目标项目：{selected_project}
- 生成数量：{quantity}条

【标注规范】:
1. **Utterance 设计**:
   - 生成自然、多样化的车载场景话术
   - 避免重复，保持语言风格一致
   - 语义要与主题相关，是连续的句子，不要含有逗号

2. **Intent 标注**:
   - 使用标准格式，如：settings_and_control:open:windows
   - 保持意图名称的规范性

3. **Slot 标注**:
   - 格式：key=value（如 temperature=26）
   - 多个slot用分号隔开
   - 如果没有参数，保持为空字符串

请以 JSON 数组格式返回：
[
  {{
    "utterance": "打开主驾驶车窗",
    "trans": "打开主驾驶侧的车窗",
    "intent": "settings_and_control:open:windows",
    "slot": "area=driver",
    "language": "{selected_language}",
    "project": "{selected_project}"
  }}
]
"""

                generated_result = call_qwen_llm(
                    system_prompt="你是一个专业的车载语音语料生成专家，只返回 JSON 数组。",
                    user_prompt=design_prompt,
                    model="qwen-max"
                )

                # 解析生成的结果
                try:
                    generated_cases = json.loads(generated_result)
                    if isinstance(generated_cases, dict) and 'items' in generated_cases:
                        generated_cases = generated_cases['items']
                except Exception as e:
                    st.error(f"❌ 结果解析失败：{generated_result}")
                    generated_cases = []

                # 保存到 session_state
                st.session_state['generated_cases'] = generated_cases

                # 显示结果
                st.success(f"✅ AI 生成了 {len(generated_cases)} 条新语料！")

                # 使用可编辑表格展示
                if generated_cases:
                    st.subheader("📝 AI 生成结果（可编辑）")
                    st.info("💡 您可以直接点击表格修改字段")

                    df_generated = pd.DataFrame(generated_cases)

                    # 确保必要的列存在
                    required_cols = ['utterance', 'trans', 'intent', 'slot', 'language', 'project']
                    for col in required_cols:
                        if col not in df_generated.columns:
                            df_generated[col] = ''

                    # 创建可编辑表格
                    edited_df = st.data_editor(
                        df_generated,
                        use_container_width=True,
                        num_rows="dynamic",
                        column_config={
                            "utterance": st.column_config.TextColumn("💬 话术", width="large"),
                            "trans": st.column_config.TextColumn("📝 中文翻译"),
                            "intent": st.column_config.TextColumn("🎯 意图"),
                            "slot": st.column_config.TextColumn("🏷️ 槽位"),
                            "language": st.column_config.TextColumn("🌐 语言", width="small"),
                            "project": st.column_config.TextColumn(" 项目", width="small")
                        },
                        hide_index=True
                    )

                    # 操作按钮
                    st.divider()
                    st.subheader("💾 导出")

                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        edited_df.to_excel(writer, index=False)

                    st.download_button(
                        label="📥 下载 Excel",
                        data=output.getvalue(),
                        file_name=f"AI_Generated_Cases_{selected_language}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                else:
                    st.warning("⚠️ AI 未生成有效结果，请调整指令后重试")

            except Exception as e:
                st.error(f"❌ 处理失败：{str(e)}")
                import traceback
                st.code(traceback.format_exc())

    elif execute_btn and not natural_query:
        st.warning("⚠️ 请输入生成指令")

# ==================== Tab 3: 批量标注 ====================

with tab_annotate:
    st.header("🪄 批量标注")
    st.info("上传待标注 Excel，AI 自动识别意图和槽位")

    # 上传文件
    task_file = st.file_uploader(
        "选择 Excel 文件 (.xlsx)",
        type=["xlsx"],
        help="Excel 文件应包含 Utterance 列",
        key="annotate_upload"
    )

    if task_file:
        try:
            df_original = pd.read_excel(task_file)

            with st.expander(" 查看文件内容", expanded=False):
                st.dataframe(df_original.head(10))
                st.write(f"✅ 成功读取 {len(df_original)} 行数据")

            st.divider()

            # 列名映射
            st.subheader("1️⃣ 列名映射")
            available_columns = list(df_original.columns)

            annotate_utterance_col = st.selectbox(
                "💬 Utterance 列",
                options=available_columns,
                help="需要标注的话术文本",
                key="annotate_utterance_col"
            )

            st.divider()

            # 开始标注
            if st.button("🚀 开始 AI 标注", type="primary", key="start_annotate"):
                if not annotate_utterance_col:
                    st.error("❌ 请选择 Utterance 列")
                else:
                    with st.spinner("🤖 AI 正在批量标注..."):
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        df_result = df_original.copy()
                        
                        # 初始化结果列
                        intent_output_col = 'AI_Intent'
                        slot_output_col = 'AI_Slot'
                        df_result[intent_output_col] = ''
                        df_result[slot_output_col] = ''

                        total_rows = len(df_result)
                        success_count = 0

                        for idx, row in df_result.iterrows():
                            try:
                                utterance = str(row.get(annotate_utterance_col, '')).strip()

                                if not utterance:
                                    continue

                                # 调用 AI 标注
                                annotation_prompt = f"""你是一个车载语音 NLU 标注专家。请为以下话术标注 Intent 和 Slot。

【待标注话术】:
{utterance}

【标注规则】:
1. **Intent**: 使用标准格式，如 settings_and_control:open:windows
2. **Slot**: 格式 key=value（如 temperature=26），多个用分号隔开，没有则留空

请以 JSON 格式返回：
{{
    "intent": "intent名称",
    "slot": "slot信息"
}}
"""

                                llm_result = call_qwen_llm(
                                    system_prompt="你是一个专业的语音标注专家，只返回 JSON 数据。",
                                    user_prompt=annotation_prompt,
                                    model="qwen-max"
                                )

                                try:
                                    annotation_data = json.loads(llm_result)
                                    ai_intent = annotation_data.get('intent', '')
                                    ai_slot = annotation_data.get('slot', '')
                                except:
                                    ai_intent = '标注失败'
                                    ai_slot = ''

                                df_result.at[idx, intent_output_col] = ai_intent
                                df_result.at[idx, slot_output_col] = ai_slot
                                success_count += 1

                            except Exception as e:
                                df_result.at[idx, intent_output_col] = f'ERROR'

                            progress = min((idx + 1) / total_rows, 1.0)
                            progress_bar.progress(progress)
                            status_text.text(f"处理进度：{idx + 1}/{total_rows} | 成功：{success_count}")

                        progress_bar.empty()
                        status_text.empty()

                        st.success(f"✅ 标注完成！成功 {success_count}/{total_rows} 条")

                        # 显示结果
                        st.subheader(" 标注结果")
                        st.dataframe(df_result, use_container_width=True)

                        # 下载
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df_result.to_excel(writer, index=False)

                        st.download_button(
                            label="📥 下载标注结果",
                            data=output.getvalue(),
                            file_name=f"AI_Annotated_{task_file.name}",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

        except Exception as e:
            st.error(f" 文件处理失败：{str(e)}")

# ==================== Tab 4: 报告分析 ====================

with tab_analysis:
    st.header(" 数据统计分析")
    st.info("上传 Excel 文件进行数据统计和可视化分析")

    report_file = st.file_uploader(
        "选择 Excel 文件 (.xlsx)",
        type=["xlsx"],
        key="report_upload"
    )

    if report_file:
        try:
            df_report = pd.read_excel(report_file)
            
            st.subheader("📊 数据概览")
            st.write(f"总行数：{len(df_report)}")
            st.write(f"总列数：{len(df_report.columns)}")
            
            st.divider()
            
            # 数值列统计
            numeric_cols = df_report.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                st.subheader("📈 数值列统计")
                st.dataframe(df_report[numeric_cols].describe())
            
            st.divider()
            
            # 数据预览
            st.subheader("📋 数据预览")
            st.dataframe(df_report.head(20), use_container_width=True)
            
            # 下载
            st.divider()
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_report.to_excel(writer, index=False)
            
            st.download_button(
                label=" 下载文件",
                data=output.getvalue(),
                file_name=f"analysis_{report_file.name}",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            st.error(f"❌ 文件处理失败：{str(e)}")

# ==================== Tab 5: 工具箱 ====================
with tab_tools:
    st.header("🛠️ 常用工具集")
    tool_type = st.radio(
        "选择工具类型",
        ["🧹 Excel 数据清洗", "🎵 音频格式转换 (M4A->WAV)", "📻 音频格式转换 (WAV->PCM)", "💿 音频格式转换 (PCM->WAV)", "📉 音频采样率转换 (48K->16K)", "🕳️ 测试 GAP 分析"],
        horizontal=True
    )

    # --- 1. Excel 数据清洗 ---
    if tool_type == "🧹 Excel 数据清洗":
        st.subheader("🧹 Excel 语料数据清洗")
        st.info("从全功能清单中提取 Case ID、ASR 和中文翻译")
        
        cleaning_file = st.file_uploader("上传 Excel 文件 (.xlsx)", type=["xlsx"], key="cleaning_upload")
        if cleaning_file:
            if st.button("开始清洗", key="start_cleaning_btn"):
                with st.spinner("正在处理..."):
                    try:
                        df = pd.read_excel(cleaning_file, sheet_name='全功能清单', engine='openpyxl')
                        cols_map = {23: 'ENU', 26: 'SPM', 29: 'PTB', 32: 'ARG'}
                        results = {lang: [] for lang in cols_map.values()}

                        def is_chinese(text):
                            return len(re.findall(r'[\u4e00-\u9fa5]', str(text))) > 0

                        for index, row in df.iterrows():
                            req_id = str(row.iloc[5]).strip() if not pd.isna(row.iloc[5]) else ""
                            for col_idx, lang in cols_map.items():
                                cell_data = row.iloc[col_idx]
                                if pd.isna(cell_data) or str(cell_data).strip() == "": continue
                                lines = str(cell_data).split('\n')
                                for line in lines:
                                    line = line.strip()
                                    if not line or line.lower().startswith('cases:'): continue
                                    first_comma = re.search(r'[,，]', line)
                                    if not first_comma: continue
                                    case_id = line[:first_comma.start()].strip()
                                    rest_of_line = line[first_comma.end():].strip()
                                    parts = [p.strip() for p in re.split(r'[,，]', rest_of_line) if p.strip()]
                                    asr_content = ""
                                    zh_translation = ""
                                    found_zh = False
                                    for i, part in enumerate(parts):
                                        if is_chinese(part):
                                            zh_translation = part
                                            asr_content = ", ".join(parts[:i])
                                            found_zh = True
                                            break
                                    if found_zh and asr_content:
                                        results[lang].append({'req_id': req_id, 'case_id': case_id, 'asr': asr_content, 'zh_translation': zh_translation})

                        output = BytesIO()
                        
                        # 创建新的 Excel workbook
                        wb = Workbook()
                        
                        # 添加各个语言sheet
                        for lang, data in results.items():
                            if data:
                                ws = wb.create_sheet(title=lang)
                                # 添加表头
                                headers = ['req_id', 'case_id', 'asr', 'zh_translation']
                                ws.append(headers)
                                # 设置表头样式
                                for cell in ws[1]:
                                    cell.font = Font(bold=True)
                                # 添加数据
                                for item in data:
                                    ws.append([item['req_id'], item['case_id'], item['asr'], item['zh_translation']])
                                # 自动筛选
                                ws.auto_filter.ref = ws.dimensions
                                # 调整列宽
                                for col_idx, col_name in enumerate(['req_id', 'case_id', 'asr', 'zh_translation'], 1):
                                    ws.column_dimensions[get_column_letter(col_idx)].width = 30
                        
                        # 添加"数据确认"sheet
                        if any(results.values()):
                            ws_confirm = wb.create_sheet(title="数据确认", index=0)
                            ws_confirm.append(['语言', '数据条数'])
                            for lang, data in results.items():
                                if data:
                                    ws_confirm.append([lang, len(data)])
                            ws_confirm.column_dimensions['A'].width = 20
                            ws_confirm.column_dimensions['B'].width = 15
                        
                        # 删除默认的Sheet
                        if 'Sheet' in wb.sheetnames:
                            del wb['Sheet']
                        
                        # 保存到 BytesIO
                        wb.save(output)
                        
                        st.success("✅ 清洗完成！")
                        st.download_button(" 下载结果", data=output.getvalue(), file_name="cleaned_result.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    except Exception as e:
                        st.error(f"❌ 处理失败: {str(e)}")

    # --- 2. M4A to WAV ---
    elif tool_type == "🎵 音频格式转换 (M4A->WAV)":
        st.subheader("🎵 M4A 转 WAV")
        m4a_files = st.file_uploader("上传 M4A 文件", type=["m4a"], accept_multiple_files=True, key="m4a_upload")
        if m4a_files:
            if st.button("开始转换", key="convert_m4a_btn"):
                progress_bar = st.progress(0)
                converted_files = []
                for i, m4a_file in enumerate(m4a_files):
                    input_path = f"temp_{m4a_file.name}"
                    output_path = os.path.splitext(input_path)[0] + ".wav"
                    with open(input_path, "wb") as f: f.write(m4a_file.getbuffer())
                    
                    command = ['ffmpeg', '-i', input_path, '-acodec', 'pcm_s16le', '-ar', '44100', '-y', output_path]
                    try:
                        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        converted_files.append((os.path.splitext(m4a_file.name)[0]+".wav", output_path))
                    except Exception as e:
                        st.error(f"转换 {m4a_file.name} 失败: {e}")
                    finally:
                        if os.path.exists(input_path): os.remove(input_path)
                    progress_bar.progress((i + 1) / len(m4a_files))
                
                if converted_files:
                    st.success(f"✅ 成功转换 {len(converted_files)} 个文件")
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for fname, fpath in converted_files:
                            zip_file.write(fpath, fname)
                            os.remove(fpath)
                    
                    st.download_button(
                        label="📥 下载全部结果 (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name="converted_wav_files.zip",
                        mime="application/zip"
                    )

    # --- 3. WAV to PCM ---
    elif tool_type == "📻 音频格式转换 (WAV->PCM)":
        st.subheader("📻 WAV 转 PCM (16k/1ch/16bit)")
        wav_files = st.file_uploader("上传 WAV 文件", type=["wav"], accept_multiple_files=True, key="wav_upload")
        if wav_files:
            if st.button("开始转换", key="convert_wav_btn"):
                converted_files = []
                for wav_file in wav_files:
                    wav_path = f"temp_{wav_file.name}"
                    with open(wav_path, "wb") as f: f.write(wav_file.getbuffer())
                    try:
                        with wave.open(wav_path, 'rb') as wf:
                            if wf.getframerate() != 16000 or wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                                st.warning(f"⚠️ {wav_file.name} 不符合 16K/单通道/16bit 要求")
                                continue
                            pcm_data = wf.readframes(wf.getnframes())
                            pcm_filename = os.path.splitext(wav_file.name)[0] + ".pcm"
                            converted_files.append((pcm_filename, pcm_data))
                    except Exception as e:
                        st.error(f"处理 {wav_file.name} 失败: {e}")
                    finally:
                        if os.path.exists(wav_path): os.remove(wav_path)
                
                if converted_files:
                    st.success(f"✅ 成功转换 {len(converted_files)} 个文件")
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for fname, fdata in converted_files:
                            zip_file.writestr(fname, fdata)
                    
                    st.download_button(
                        label="📥 下载全部结果 (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name="converted_pcm_files.zip",
                        mime="application/zip"
                    )

    # --- 4. PCM to WAV ---
    elif tool_type == "💿 音频格式转换 (PCM->WAV)":
        st.subheader("💿 PCM 转 WAV")
        st.info("将原始 PCM 音频数据封装为标准的 WAV 格式")
        
        pcm_files = st.file_uploader("上传 PCM 文件", type=["pcm"], accept_multiple_files=True, key="pcm_upload")
        
        col_pcm1, col_pcm2 = st.columns(2)
        with col_pcm1:
            sample_rate = st.number_input("采样率 (Hz)", value=16000, step=1000)
        with col_pcm2:
            channels = st.number_input("声道数", value=1, min_value=1, max_value=2)
        
        if pcm_files:
            if st.button("开始转换", key="convert_pcm_btn"):
                converted_files = []
                for pcm_file in pcm_files:
                    pcm_path = f"temp_{pcm_file.name}"
                    with open(pcm_path, "wb") as f: f.write(pcm_file.getbuffer())
                    try:
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
                        st.error(f"处理 {pcm_file.name} 失败: {e}")
                    finally:
                        if os.path.exists(pcm_path): os.remove(pcm_path)
                
                if converted_files:
                    st.success(f"✅ 成功转换 {len(converted_files)} 个文件")
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for fname, fpath in converted_files:
                            zip_file.write(fpath, fname)
                            os.remove(fpath)
                    
                    st.download_button(
                        label="📥 下载全部结果 (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name="converted_wav_from_pcm.zip",
                        mime="application/zip"
                    )

    # --- 5. 48K to 16K ---
    elif tool_type == "📉 音频采样率转换 (48K->16K)":
        st.subheader("📉 音频采样率转换 (48K -> 16K)")
        
        audio_files_48k = st.file_uploader("上传音频文件", type=["wav", "m4a", "mp3"], accept_multiple_files=True, key="resample_upload")
        if audio_files_48k:
            if st.button("开始重采样", key="resample_btn"):
                progress_bar = st.progress(0)
                converted_files = []
                for i, audio_file in enumerate(audio_files_48k):
                    input_path = f"temp_{audio_file.name}"
                    output_filename = f"16k_{os.path.splitext(audio_file.name)[0]}.wav"
                    output_path = f"temp_{output_filename}"
                    
                    with open(input_path, "wb") as f: f.write(audio_file.getbuffer())
                    
                    command = ['ffmpeg', '-i', input_path, '-ar', '16000', '-ac', '1', '-y', output_path]
                    try:
                        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        converted_files.append((output_filename, output_path))
                    except Exception as e:
                        st.error(f"转换 {audio_file.name} 失败: {e}")
                    finally:
                        if os.path.exists(input_path): os.remove(input_path)
                    progress_bar.progress((i + 1) / len(audio_files_48k))
                
                if converted_files:
                    st.success(f"✅ 成功转换 {len(converted_files)} 个文件")
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for fname, fpath in converted_files:
                            zip_file.write(fpath, fname)
                            os.remove(fpath)
                    
                    st.download_button(
                        label="📥 下载全部结果 (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name="resampled_16k_files.zip",
                        mime="application/zip"
                    )

    # --- 6. GAP Analysis ---
    elif tool_type == "🕳️ 测试 GAP 分析":
        st.subheader("🕳️ 测试报告 GAP 分析")
        st.info("对比测试报告与优先级清单，找出缺失的 Req ID")
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            report_file_gap = st.file_uploader("上传测试报告", type=["xlsx"], key="gap_report")
        with col_g2:
            priority_file_gap = st.file_uploader("上传优先级清单", type=["xlsx"], key="gap_priority")
        
        priorities = st.multiselect("选择 Priority", ['P0', 'P1', 'P2', 'P4'], default=['P0', 'P1'])
        min_pass = st.number_input("最小 Pass 数量", min_value=1, value=1)
        
        if report_file_gap and priority_file_gap:
            if st.button("开始分析 GAP", key="analyze_gap_btn"):
                with st.spinner("正在分析..."):
                    try:
                        report_df = pd.read_excel(report_file_gap, sheet_name='All', skiprows=1)
                        priority_df = pd.read_excel(priority_file_gap, sheet_name='ReqID VS P0,1,2,4', skiprows=2)
                        
                        target_req_ids = set()
                        for priority in priorities:
                            filtered_reqs = priority_df[priority_df.iloc[:, 3] == priority].iloc[:, 2]
                            target_req_ids.update(filtered_reqs.dropna().astype(str))
                        
                        req_pass_counts = {}
                        for idx, row in report_df.iterrows():
                            req_id = str(row.iloc[0])
                            final_res = row.iloc[16]
                            if req_id in target_req_ids:
                                if req_id not in req_pass_counts: req_pass_counts[req_id] = 0
                                if final_res == 'P': req_pass_counts[req_id] += 1
                        
                        missing_req_ids = [rid for rid in target_req_ids if rid not in req_pass_counts]
                        insufficient_req_ids = [(rid, cnt) for rid, cnt in req_pass_counts.items() if cnt < min_pass]
                        
                        st.markdown("### 📊 分析结果")
                        if missing_req_ids:
                            st.markdown("**需要补充的 req_id:**")
                            st.code("\n".join(sorted(missing_req_ids)))
                        else:
                            st.success("所有目标 req_id 在报告中都有对应的 case")
                        
                        if insufficient_req_ids:
                            st.markdown(f"**不满足最小 Pass 数量 ({min_pass}个):**")
                            df_insuf = pd.DataFrame(insufficient_req_ids, columns=['Req ID', 'Pass Count'])
                            st.dataframe(df_insuf.sort_values(by='Req ID'))
                        else:
                            st.success(f"所有目标 req_id 都满足最小 Pass 数量 ({min_pass}个)")
                    except Exception as e:
                        st.error(f"❌ 分析失败: {str(e)}")

# ==================== 底部信息 ====================

st.markdown("---")
st.caption("Powered by Streamlit + 千问大模型 | Version 2.0")
