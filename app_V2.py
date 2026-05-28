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
import wave
from openpyxl.utils import get_column_letter
from openpyxl import Workbook
from openpyxl.styles import Font
import zipfile
import time
import base64
import hashlib
import csv

# ==================== 1. 配置与初始化 ====================

st.set_page_config(
    page_title="AI智能测试与办公提效平台",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 默认的千问 API Key
DEFAULT_API_KEY = "sk-e10cbbca48ea4f23a590884e59b3d7c9"

# ==================== 2. 侧边栏 - API Key 配置 ====================

with st.sidebar:
    st.header("️ 系统配置")
    
    api_key_mode = st.radio(
        "🔑 API Key 模式",
        options=["默认 API Key", "自定义 API Key"],
        help="选择使用默认配置的 API Key 或自己输入",
        index=0
    )
    
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
    
    os.environ['NO_PROXY'] = '*'
    http_client = httpx.Client(verify=False, timeout=60.0, trust_env=False)
    
    client_qwen = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        http_client=http_client
    )
    
    if api_key:
        dashscope.api_key = api_key
        st.success("✅ API Key 已配置")
    else:
        st.warning("⚠️ 请先配置 API Key")
    
    st.divider()
    
    st.markdown("""
    ### 📖 功能说明
    
    ** AI测试助手**
    - 测试用例生成
    - Bug智能分析  
    - 测试报告生成
    
    ** 办公提效工具**
    - 文件格式转换
    - 数据处理工具
    - 文本处理工具
    - 编码解码工具
    
    ** 音频工具箱**
    - M4A/WAV/PCM互转
    - 采样率转换
    """)

# ==================== 3. 工具函数 ====================

def init_session_state():
    """初始化 session state"""
    if 'test_cases' not in st.session_state:
        st.session_state['test_cases'] = []

init_session_state()

def call_qwen_llm(system_prompt: str, user_prompt: str, model: str = "qwen-max"):
    """调用千问大模型"""
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

# ==================== 4. 主页面布局 ====================

st.title(" AI智能测试与办公提效平台")
st.markdown("---")

# 创建三个功能模块标签页
tab_ai_test, tab_office, tab_audio = st.tabs([
    " AI测试助手",
    "️ 办公提效工具",
    " 音频工具箱"
])

# ==================== Tab 1: AI测试助手 ====================

with tab_ai_test:
    st.header(" AI测试助手")
    st.info("利用AI大模型提升测试效率")
    
    ai_test_tool = st.radio(
        "选择AI测试工具",
        [" 测试用例生成", "🐛 Bug智能分析", " 测试报告生成"],
        horizontal=True
    )
    
    # --- 1. 测试用例生成 ---
    if ai_test_tool == " 测试用例生成":
        st.subheader(" 测试用例生成")
        
        test_type = st.selectbox(
            "测试类型",
            ["功能测试", "接口测试", "UI测试", "性能测试"]
        )
        
        requirement = st.text_area(
            "输入需求描述",
            placeholder="例如：用户登录功能，支持手机号和邮箱登录，密码需要包含大小写字母和数字...",
            height=150
        )
        
        if st.button(" 生成测试用例", type="primary"):
            if not requirement:
                st.warning("⚠️ 请输入需求描述")
            else:
                with st.spinner(" AI正在生成测试用例..."):
                    prompt = f"""你是一个资深测试专家。请根据以下需求生成详细的测试用例。

【需求描述】:
{requirement}

【测试类型】: {test_type}

请生成结构化的测试用例，包含:
1. 用例编号
2. 用例标题
3. 前置条件
4. 测试步骤
5. 预期结果
6. 优先级(P0/P1/P2)

以JSON数组格式返回：
[
  {{
    "id": "TC001",
    "title": "用例标题",
    "precondition": "前置条件",
    "steps": ["步骤1", "步骤2"],
    "expected": "预期结果",
    "priority": "P0"
  }}
]
"""
                    
                    result = call_qwen_llm(
                        system_prompt="你是一个专业的测试工程师，只返回JSON数据。",
                        user_prompt=prompt,
                        model="qwen-max"
                    )
                    
                    try:
                        test_cases = json.loads(result)
                        if isinstance(test_cases, dict) and 'items' in test_cases:
                            test_cases = test_cases['items']
                        
                        st.session_state['test_cases'] = test_cases
                        st.success(f"✅ 成功生成 {len(test_cases)} 条测试用例！")
                        
                        if test_cases:
                            df = pd.DataFrame(test_cases)
                            st.dataframe(df, use_container_width=True)
                            
                            # 导出Excel
                            output = BytesIO()
                            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                df.to_excel(writer, index=False)
                            
                            st.download_button(
                                label=" 下载测试用例Excel",
                                data=output.getvalue(),
                                file_name="test_cases.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                    except Exception as e:
                        st.error(f" 解析失败：{result}")
    
    # --- 2. Bug智能分析 ---
    elif ai_test_tool == "🐛 Bug智能分析":
        st.subheader("🐛 Bug智能分析")
        
        bug_title = st.text_input("Bug标题")
        bug_description = st.text_area(
            "Bug描述/日志",
            placeholder="粘贴Bug描述、错误日志或堆栈信息...",
            height=200
        )
        
        if st.button("🐛 分析Bug", type="primary"):
            if not bug_description:
                st.warning("⚠️ 请输入Bug描述")
            else:
                with st.spinner("🤖 AI正在分析Bug..."):
                    prompt = f"""你是一个资深开发工程师。请分析以下Bug信息。

【Bug标题】: {bug_title}

【Bug描述/日志】:
{bug_description}

请分析并提供:
1. **问题根因**: 分析可能的根本原因
2. **影响范围**: 评估影响的功能模块
3. **修复建议**: 提供具体的修复方案
4. **优先级评估**: P0/P1/P2/P3
5. **预防措施**: 如何避免类似问题

请以清晰的格式返回分析结果。
"""
                    
                    result = call_qwen_llm(
                        system_prompt="你是一个专业的开发工程师，擅长Bug分析和定位。",
                        user_prompt=prompt,
                        model="qwen-max"
                    )
                    
                    st.markdown("### 分析结果")
                    st.markdown(result)
    
    # --- 3. 测试报告生成 ---
    elif ai_test_tool == " 测试报告生成":
        st.subheader(" 测试报告生成")
        
        project_name = st.text_input("项目名称")
        test_summary = st.text_area(
            "测试概况",
            placeholder="例如：共执行100个用例，通过85个，失败15个，阻塞0个...",
            height=100
        )
        
        bug_list = st.text_area(
            "Bug清单",
            placeholder="例如：\nBUG-001: 登录页面无法提交 P0\nBUG-002: 首页加载慢 P1...",
            height=150
        )
        
        if st.button(" 生成测试报告", type="primary"):
            if not test_summary:
                st.warning("️ 请输入测试概况")
            else:
                with st.spinner(" AI正在生成测试报告..."):
                    prompt = f"""你是一个测试经理。请根据以下信息生成专业的测试报告。

【项目名称】: {project_name}

【测试概况】:
{test_summary}

【Bug清单】:
{bug_list}

请生成结构化的测试报告，包含:
1. 测试概述
2. 测试执行统计
3. 缺陷分析
4. 风险评估
5. 测试结论
6. 建议与改进措施

格式要求：使用Markdown格式，包含表格和图表说明。
"""
                    
                    result = call_qwen_llm(
                        system_prompt="你是一个专业的测试经理，擅长编写测试报告。",
                        user_prompt=prompt,
                        model="qwen-max"
                    )
                    
                    st.markdown("### 测试报告")
                    st.markdown(result)
                    
                    # 导出Markdown
                    st.download_button(
                        label=" 下载测试报告",
                        data=result,
                        file_name=f"{project_name}_test_report.md",
                        mime="text/markdown"
                    )

# ==================== Tab 2: 办公提效工具 ====================

with tab_office:
    st.header("️ 办公提效工具")
    st.info("日常办公高频需求，一键解决")
    
    office_tool = st.radio(
        "选择办公工具",
        [" 文件格式转换", " 数据处理", "📝 文本处理", " 编码解码"],
        horizontal=True
    )
    
    # --- 1. 文件格式转换 ---
    if office_tool == " 文件格式转换":
        st.subheader(" 文件格式转换")
        
        convert_type = st.selectbox(
            "转换类型",
            ["Excel → CSV", "CSV → Excel", "JSON 格式化", "XML 格式化"]
        )
        
        if convert_type == "Excel → CSV":
            excel_file = st.file_uploader("上传Excel文件", type=["xlsx"], key="excel_to_csv")
            if excel_file:
                if st.button("开始转换", key="convert_excel_csv"):
                    df = pd.read_excel(excel_file)
                    csv_output = df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label=" 下载CSV文件",
                        data=csv_output,
                        file_name=f"{excel_file.name.replace('.xlsx', '.csv')}",
                        mime="text/csv"
                    )
                    st.success("✅ 转换完成！")
        
        elif convert_type == "CSV → Excel":
            csv_file = st.file_uploader("上传CSV文件", type=["csv"], key="csv_to_excel")
            if csv_file:
                if st.button("开始转换", key="convert_csv_excel"):
                    df = pd.read_csv(csv_file, encoding='utf-8-sig')
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False)
                    st.download_button(
                        label=" 下载Excel文件",
                        data=output.getvalue(),
                        file_name=f"{csv_file.name.replace('.csv', '.xlsx')}",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    st.success("✅ 转换完成！")
        
        elif convert_type == "JSON 格式化":
            json_input = st.text_area("输入JSON", height=200)
            if json_input and st.button("格式化", key="format_json"):
                try:
                    json_obj = json.loads(json_input)
                    formatted = json.dumps(json_obj, indent=2, ensure_ascii=False)
                    st.code(formatted, language="json")
                    st.download_button(
                        label=" 下载格式化JSON",
                        data=formatted,
                        file_name="formatted.json",
                        mime="application/json"
                    )
                    st.success("✅ 格式化成功！")
                except Exception as e:
                    st.error(f"❌ JSON格式错误：{str(e)}")
        
        elif convert_type == "XML 格式化":
            xml_input = st.text_area("输入XML", height=200)
            if xml_input and st.button("格式化", key="format_xml"):
                try:
                    import xml.dom.minidom
                    dom = xml.dom.minidom.parseString(xml_input)
                    formatted = dom.toprettyxml(indent="  ")
                    st.code(formatted, language="xml")
                    st.download_button(
                        label=" 下载格式化XML",
                        data=formatted,
                        file_name="formatted.xml",
                        mime="application/xml"
                    )
                    st.success("✅ 格式化成功！")
                except Exception as e:
                    st.error(f"❌ XML格式错误：{str(e)}")
    
    # --- 2. 数据处理 ---
    elif office_tool == " 数据处理":
        st.subheader(" 数据处理")
        
        data_tool = st.selectbox(
            "数据处理功能",
            ["Excel多表合并", "数据去重对比", "批量替换"]
        )
        
        if data_tool == "Excel多表合并":
            st.info("上传多个Excel文件，合并为一个文件")
            excel_files = st.file_uploader(
                "上传Excel文件", 
                type=["xlsx"], 
                accept_multiple_files=True,
                key="merge_excel"
            )
            if excel_files and len(excel_files) > 1:
                if st.button("开始合并", key="start_merge"):
                    merged_df = pd.DataFrame()
                    for file in excel_files:
                        df = pd.read_excel(file)
                        df['来源文件'] = file.name
                        merged_df = pd.concat([merged_df, df], ignore_index=True)
                    
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        merged_df.to_excel(writer, index=False)
                    
                    st.download_button(
                        label=" 下载合并结果",
                        data=output.getvalue(),
                        file_name="merged_result.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    st.success(f"✅ 成功合并 {len(excel_files)} 个文件，共 {len(merged_df)} 行数据！")
        
        elif data_tool == "数据去重对比":
            st.info("上传两个Excel文件，对比差异")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                file1 = st.file_uploader("文件1", type=["xlsx"], key="compare_file1")
            with col_f2:
                file2 = st.file_uploader("文件2", type=["xlsx"], key="compare_file2")
            
            if file1 and file2:
                if st.button("开始对比", key="start_compare"):
                    df1 = pd.read_excel(file1)
                    df2 = pd.read_excel(file2)
                    
                    # 查找差异
                    only_in_1 = pd.merge(df1, df2, how='left', indicator=True)
                    only_in_1 = only_in_1[only_in_1['_merge'] == 'left_only']
                    
                    only_in_2 = pd.merge(df2, df1, how='left', indicator=True)
                    only_in_2 = only_in_2[only_in_2['_merge'] == 'left_only']
                    
                    st.markdown(f"### 对比结果")
                    st.write(f"📊 文件1独有数据：{len(only_in_1)} 行")
                    st.write(f" 文件2独有数据：{len(only_in_2)} 行")
                    
                    # 导出差异
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        if len(only_in_1) > 0:
                            only_in_1.to_excel(writer, sheet_name='仅在文件1', index=False)
                        if len(only_in_2) > 0:
                            only_in_2.to_excel(writer, sheet_name='仅在文件2', index=False)
                    
                    st.download_button(
                        label=" 下载对比结果",
                        data=output.getvalue(),
                        file_name="compare_result.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        
        elif data_tool == "批量替换":
            st.info("在Excel中批量替换文本")
            replace_file = st.file_uploader("上传Excel文件", type=["xlsx"], key="replace_file")
            if replace_file:
                col_old, col_new = st.columns(2)
                with col_old:
                    old_text = st.text_input("查找内容")
                with col_new:
                    new_text = st.text_input("替换为")
                
                if old_text and new_text and st.button("开始替换", key="start_replace"):
                    df = pd.read_excel(replace_file)
                    df_replaced = df.replace(old_text, new_text, regex=True)
                    
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_replaced.to_excel(writer, index=False)
                    
                    st.download_button(
                        label=" 下载替换结果",
                        data=output.getvalue(),
                        file_name="replaced_result.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    st.success("✅ 替换完成！")
    
    # --- 3. 文本处理 ---
    elif office_tool == "📝 文本处理":
        st.subheader("📝 文本处理")
        
        text_tool = st.selectbox(
            "文本处理功能",
            ["批量查找替换", "文本去重", "文本排序", "正则表达式测试"]
        )
        
        if text_tool == "批量查找替换":
            text_input = st.text_area("输入文本", height=200)
            col_f, col_r = st.columns(2)
            with col_f:
                find_text = st.text_input("查找")
            with col_r:
                replace_text = st.text_input("替换为")
            
            if text_input and find_text and st.button("替换", key="text_replace"):
                result = text_input.replace(find_text, replace_text)
                st.text_area("结果", value=result, height=200)
                st.download_button(
                    label=" 下载结果",
                    data=result,
                    file_name="replaced.txt",
                    mime="text/plain"
                )
        
        elif text_tool == "文本去重":
            text_input = st.text_area("输入文本(每行一条)", height=200)
            if text_input and st.button("去重", key="text_deduplicate"):
                lines = text_input.split('\n')
                unique_lines = list(dict.fromkeys(lines))  # 保持顺序去重
                result = '\n'.join(unique_lines)
                st.text_area(f"结果(去重前:{len(lines)}行, 去重后:{len(unique_lines)}行)", 
                            value=result, height=200)
        
        elif text_tool == "文本排序":
            text_input = st.text_area("输入文本(每行一条)", height=200)
            sort_type = st.radio("排序方式", ["升序", "降序"])
            if text_input and st.button("排序", key="text_sort"):
                lines = text_input.split('\n')
                lines = [l for l in lines if l.strip()]  # 移除空行
                lines.sort(reverse=(sort_type == "降序"))
                result = '\n'.join(lines)
                st.text_area("排序结果", value=result, height=200)
        
        elif text_tool == "正则表达式测试":
            st.info("测试正则表达式匹配")
            pattern = st.text_input("正则表达式", placeholder="例如：\\d+ 匹配数字")
            text_input = st.text_area("测试文本", height=150)
            
            if pattern and text_input and st.button("测试匹配", key="test_regex"):
                try:
                    matches = re.findall(pattern, text_input)
                    st.success(f"✅ 找到 {len(matches)} 个匹配")
                    if matches:
                        for i, match in enumerate(matches, 1):
                            st.write(f"{i}. {match}")
                except Exception as e:
                    st.error(f"❌ 正则表达式错误：{str(e)}")
    
    # --- 4. 编码解码 ---
    elif office_tool == "🔐 编码解码":
        st.subheader("🔐 编码解码")
        
        encode_tool = st.selectbox(
            "编解码功能",
            ["Base64 编码", "Base64 解码", "URL 编码", "URL 解码", "MD5 加密", "SHA256 加密"]
        )
        
        text_input = st.text_area("输入文本", height=150)
        
        if text_input:
            if encode_tool == "Base64 编码":
                result = base64.b64encode(text_input.encode()).decode()
                st.code(result)
                st.download_button(" 下载结果", data=result, file_name="base64.txt")
            
            elif encode_tool == "Base64 解码":
                try:
                    result = base64.b64decode(text_input).decode()
                    st.code(result)
                except Exception as e:
                    st.error(f"❌ 解码失败：{str(e)}")
            
            elif encode_tool == "URL 编码":
                from urllib.parse import quote
                result = quote(text_input)
                st.code(result)
            
            elif encode_tool == "URL 解码":
                from urllib.parse import unquote
                result = unquote(text_input)
                st.code(result)
            
            elif encode_tool == "MD5 加密":
                result = hashlib.md5(text_input.encode()).hexdigest()
                st.code(result)
            
            elif encode_tool == "SHA256 加密":
                result = hashlib.sha256(text_input.encode()).hexdigest()
                st.code(result)

# ==================== Tab 3: 音频工具箱 ====================

with tab_audio:
    st.header(" 音频工具箱")
    st.info("音频格式转换与处理")
    
    audio_tool = st.radio(
        "选择音频工具",
        [" M4A → WAV", " WAV → PCM", "💿 PCM → WAV", "📉 48K → 16K"],
        horizontal=True
    )
    
    # --- 1. M4A to WAV ---
    if audio_tool == "🎵 M4A → WAV":
        st.subheader(" M4A 转 WAV")
        m4a_files = st.file_uploader("上传 M4A 文件", type=["m4a"], accept_multiple_files=True, key="m4a_upload")
        if m4a_files:
            if st.button("开始转换", key="convert_m4a_btn"):
                progress_bar = st.progress(0)
                converted_files = []
                for i, m4a_file in enumerate(m4a_files):
                    input_path = f"temp_{m4a_file.name}"
                    output_path = os.path.splitext(input_path)[0] + ".wav"
                    with open(input_path, "wb") as f:
                        f.write(m4a_file.getbuffer())
                    
                    command = ['ffmpeg', '-i', input_path, '-acodec', 'pcm_s16le', '-ar', '44100', '-y', output_path]
                    try:
                        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        converted_files.append((os.path.splitext(m4a_file.name)[0]+".wav", output_path))
                    except Exception as e:
                        st.error(f"转换 {m4a_file.name} 失败: {e}")
                    finally:
                        if os.path.exists(input_path):
                            os.remove(input_path)
                    progress_bar.progress((i + 1) / len(m4a_files))
                
                if converted_files:
                    st.success(f"✅ 成功转换 {len(converted_files)} 个文件")
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for fname, fpath in converted_files:
                            zip_file.write(fpath, fname)
                            os.remove(fpath)
                    
                    st.download_button(
                        label=" 下载全部结果 (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name="converted_wav_files.zip",
                        mime="application/zip"
                    )
    
    # --- 2. WAV to PCM ---
    elif audio_tool == " WAV → PCM":
        st.subheader("📻 WAV 转 PCM (16k/1ch/16bit)")
        wav_files = st.file_uploader("上传 WAV 文件", type=["wav"], accept_multiple_files=True, key="wav_upload")
        if wav_files:
            if st.button("开始转换", key="convert_wav_btn"):
                converted_files = []
                for wav_file in wav_files:
                    wav_path = f"temp_{wav_file.name}"
                    with open(wav_path, "wb") as f:
                        f.write(wav_file.getbuffer())
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
                        if os.path.exists(wav_path):
                            os.remove(wav_path)
                
                if converted_files:
                    st.success(f"✅ 成功转换 {len(converted_files)} 个文件")
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for fname, fdata in converted_files:
                            zip_file.writestr(fname, fdata)
                    
                    st.download_button(
                        label=" 下载全部结果 (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name="converted_pcm_files.zip",
                        mime="application/zip"
                    )
    
    # --- 3. PCM to WAV ---
    elif audio_tool == "💿 PCM → WAV":
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
                    with open(pcm_path, "wb") as f:
                        f.write(pcm_file.getbuffer())
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
                        if os.path.exists(pcm_path):
                            os.remove(pcm_path)
                
                if converted_files:
                    st.success(f"✅ 成功转换 {len(converted_files)} 个文件")
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for fname, fpath in converted_files:
                            zip_file.write(fpath, fname)
                            os.remove(fpath)
                    
                    st.download_button(
                        label=" 下载全部结果 (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name="converted_wav_from_pcm.zip",
                        mime="application/zip"
                    )
    
    # --- 4. 48K to 16K ---
    elif audio_tool == "📉 48K → 16K":
        st.subheader("📉 音频采样率转换 (48K → 16K)")
        
        audio_files_48k = st.file_uploader("上传音频文件", type=["wav", "m4a", "mp3"], accept_multiple_files=True, key="resample_upload")
        if audio_files_48k:
            if st.button("开始重采样", key="resample_btn"):
                progress_bar = st.progress(0)
                converted_files = []
                for i, audio_file in enumerate(audio_files_48k):
                    input_path = f"temp_{audio_file.name}"
                    output_filename = f"16k_{os.path.splitext(audio_file.name)[0]}.wav"
                    output_path = f"temp_{output_filename}"
                    
                    with open(input_path, "wb") as f:
                        f.write(audio_file.getbuffer())
                    
                    command = ['ffmpeg', '-i', input_path, '-ar', '16000', '-ac', '1', '-y', output_path]
                    try:
                        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        converted_files.append((output_filename, output_path))
                    except Exception as e:
                        st.error(f"转换 {audio_file.name} 失败: {e}")
                    finally:
                        if os.path.exists(input_path):
                            os.remove(input_path)
                    progress_bar.progress((i + 1) / len(audio_files_48k))
                
                if converted_files:
                    st.success(f"✅ 成功转换 {len(converted_files)} 个文件")
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for fname, fpath in converted_files:
                            zip_file.write(fpath, fname)
                            os.remove(fpath)
                    
                    st.download_button(
                        label=" 下载全部结果 (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name="resampled_16k_files.zip",
                        mime="application/zip"
                    )

# ==================== 底部信息 ====================

st.markdown("---")
st.caption("Powered by Streamlit + 千问大模型 | Version 3.0 - AI智能测试与办公提效平台")
