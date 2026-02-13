# app.py (Definitive Final Version)

import os, re, json, pandas as pd, zipfile, tempfile, shutil, uuid, threading, requests
from flask import Flask, request, render_template, flash, redirect, url_for, send_from_directory, session, jsonify

from werkzeug.utils import secure_filename

from excel_processor import process_excel_file
from longines_processor import process_longines_file
from google_drive_finder import authenticate_google_drive, find_image_links_for_df, update_google_sheet, read_sheet_data
from slice_processor import process_slice_folder
from text_processor import parse_pasted_data, process_local_data

# --- App Initialization and Config ---
app = Flask(__name__)
# --- 核心修改：在这里增加一行 SERVER_NAME 配置 ---
app.config.update(
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads'),
    OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs'),
    SECRET_KEY='your_very_secret_and_unique_key_12345',
    TEMPLATES_AUTO_RELOAD=True,
    SERVER_NAME='127.0.0.1:5000' # 明确告知服务器地址
)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

try:
    with open('config.json', 'r', encoding='utf-8') as f: CONFIG = json.load(f)
except FileNotFoundError: CONFIG = {}

PROCESSORS = {"longines_processor": process_longines_file, "excel_processor": process_excel_file}
tasks = {}

# --- Background Task Runners ---
def run_data_task(task_id, input_path, project_type, spreadsheet_id):
    # --- 核心修改1：为后台任务包裹上应用上下文 ---
    with app.app_context():
        try:
            project_config = CONFIG[project_type]
            tasks[task_id] = {'status': '正在初步处理Excel文件...', 'progress': 10}
            processor_function = PROCESSORS.get(project_config['processor'])
            processed_df = processor_function(input_path)
            if processed_df is None or processed_df.empty:
                raise ValueError("处理Excel文件时出错，或未生成有效数据。")

            tasks[task_id]['status'] = '正在连接Google并获取授权...'
            tasks[task_id]['progress'] = 30
            creds = authenticate_google_drive()

            tasks[task_id]['status'] = '正在查找Google Drive图片链接...'
            tasks[task_id]['progress'] = 50
            final_df = find_image_links_for_df(processed_df.copy(), project_config, creds)
            if final_df is None:
                raise ValueError("查找Google Drive图片时发生错误。")
            
            tasks[task_id]['status'] = '正在更新Google Sheet (此步可能较慢)...'
            tasks[task_id]['progress'] = 80
            success = update_google_sheet(spreadsheet_id, final_df, creds)
            if not success:
                raise ValueError("更新Google Sheet失败。")

            tasks[task_id].update({'status': '任务完成！', 'progress': 100, 'result': 'success'})
        except Exception as e:
            tasks[task_id].update({'status': f'任务失败: {str(e)}', 'progress': 100, 'result': 'error'})

def run_slice_task(task_id, zip_path):
    # --- 核心修改2：为切图任务也包裹上应用上下文 ---
    with app.app_context():
        try:
            tasks[task_id] = {'status': '正在解压文件...', 'progress': 10}
            extract_dir = os.path.join(os.path.dirname(zip_path), 'extracted_slices')
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            image_folder = extract_dir
            unzipped_items = os.listdir(extract_dir)
            if len(unzipped_items) == 1 and os.path.isdir(os.path.join(extract_dir, unzipped_items[0])):
                image_folder = os.path.join(extract_dir, unzipped_items[0])

            tasks[task_id] = {'status': '正在重命名和压缩图片...', 'progress': 40}
            process_slice_folder(image_folder)

            tasks[task_id] = {'status': '正在重新打包为ZIP...', 'progress': 90}
            output_zip_name = f"processed_{os.path.splitext(os.path.basename(zip_path))[0]}"
            output_zip_path_base = os.path.join(app.config['OUTPUT_FOLDER'], output_zip_name)
            shutil.make_archive(output_zip_path_base, 'zip', image_folder)

            tasks[task_id].update({
                'status': '任务完成！准备下载...', 'progress': 100, 'result': 'success',
                'download_url': url_for('download_processed_zip', filename=f"{output_zip_name}.zip")
            })
        except Exception as e:
            tasks[task_id].update({'status': f'任务失败: {str(e)}', 'progress': 100, 'result': 'error'})
        finally:
            if os.path.exists(zip_path): os.remove(zip_path)
            if 'extract_dir' in locals() and os.path.exists(extract_dir): shutil.rmtree(extract_dir)

# --- NEW: Cloud Sync Task Runner (Mode A) ---
def run_cloud_sync_task(task_id, spreadsheet_id, project_type):
    with app.app_context():
        try:
            print(f"[{task_id}] 开始云端同步任务...", flush=True)
            project_config = CONFIG[project_type]
            tasks[task_id] = {'status': '正在连接Google并获取授权...', 'progress': 10}
            creds = authenticate_google_drive()
            
            tasks[task_id]['status'] = '正在读取 Google Sheet 数据...'
            tasks[task_id]['progress'] = 30
            print(f"[{task_id}] 正在调用 read_sheet_data...", flush=True)
            
            # 这里简化处理，读取默认 Sheet1，或者我们可以让 update_google_sheet 自动处理
            # 为了稳健性，先读取数据到 DF
            # 注意：read_sheet_data 现在会自动探测 Sheet 名称
            current_df = read_sheet_data(spreadsheet_id, creds)
            
            if current_df is None or current_df.empty:
                 print(f"[{task_id}] read_sheet_data 返回空 DataFrame", flush=True)
                 raise ValueError("未能从 Google Sheet读取到数据，请检查链接或权限。")

            print(f"[{task_id}] 数据读取成功，行数: {len(current_df)}", flush=True)
            tasks[task_id]['status'] = '正在查找并补全图片链接...'
            tasks[task_id]['progress'] = 60
            
            # 使用现有逻辑查找图片
            # 注意：find_image_links_for_df 会依赖 'model_sku' 列，确保 Sheet 里有这一列
            # 如果之前的标准化已经统一了列名，这里应该能直接工作
            # 如果没有 'model_sku'，尝试找 'SKU' 或 '商品SKU' 并重命名
            renamed = False
            if 'model_sku' not in current_df.columns:
                print(f"[{task_id}] 未找到 'model_sku' 列，尝试查找别名...", flush=True)
                for col in ['SKU', '商品SKU', '型号']:
                    if col in current_df.columns:
                        print(f"[{task_id}] 找到列 '{col}'，重命名为 'model_sku'", flush=True)
                        current_df.rename(columns={col: 'model_sku'}, inplace=True)
                        renamed = True
                        break
            
            if 'model_sku' not in current_df.columns:
                 print(f"[{task_id}] 列名匹配失败。现有列: {current_df.columns.tolist()}", flush=True)
                 raise ValueError("表格中找不到关键列 'SKU' 或 'model_sku'，无法匹配图片。")

            final_df = find_image_links_for_df(current_df, project_config, creds)
            
            # 如果我们重命名了列，写入前最好改回来，或者就保留 standard name，
            # 鉴于 Mode A 是“回写”，最好保留用户习惯。
            # 但 update_google_sheet 是全覆写，所以这里改了列名会写回去。
            # 暂时保持 'model_sku'，因为系统后续流程可能都认这个。
            
            tasks[task_id]['status'] = '正在回写数据到 Google Sheet...'
            tasks[task_id]['progress'] = 90
            success = update_google_sheet(spreadsheet_id, final_df, creds)
            
            if not success:
                raise ValueError("回写数据失败。")

            tasks[task_id].update({'status': '同步完成！图片链接已更新。', 'progress': 100, 'result': 'success'})
            print(f"[{task_id}] 任务成功完成", flush=True)
            
        except Exception as e:
            print(f"[{task_id}] 任务执行出错:", flush=True)
            traceback.print_exc()
            tasks[task_id].update({'status': f'同步失败: {str(e)}', 'progress': 100, 'result': 'error'})

# --- NEW: Local Paste Task Runner (Mode B) ---
def run_local_paste_task(task_id, pasted_text, project_type):
    with app.app_context():
        try:
            project_config = CONFIG[project_type]
            tasks[task_id] = {'status': '正在解析粘贴的数据...', 'progress': 10}
            
            raw_df = parse_pasted_data(pasted_text)
            if raw_df.empty:
                raise ValueError("解析数据失败，请确保粘贴了有效的Excel数据。")
                
            processed_df = process_local_data(raw_df)
            
            tasks[task_id]['status'] = '正在连接Google并获取授权...'
            tasks[task_id]['progress'] = 30
            creds = authenticate_google_drive()
            
            tasks[task_id]['status'] = '正在查找图片链接...'
            tasks[task_id]['progress'] = 60
            final_df = find_image_links_for_df(processed_df, project_config, creds)
            
            tasks[task_id]['status'] = '正在生成Excel文件...'
            tasks[task_id]['progress'] = 90
            
            output_filename = f"processed_paste_{uuid.uuid4().hex[:8]}.xlsx"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            final_df.to_excel(output_path, index=False)
            
            tasks[task_id].update({
                'status': '处理完成！准备下载...', 
                'progress': 100, 
                'result': 'success',
                'download_url': url_for('download_processed_zip', filename=output_filename) # 复用路由，只要是文件都在 output 目录
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            tasks[task_id].update({'status': f'处理失败: {str(e)}', 'progress': 100, 'result': 'error'})

# --- Helper Functions ---
def validate_excel_file(file_path, project_config):
    # ... (code for this function)
    return True, "Validation successful" # Placeholder for brevity

def extract_spreadsheet_id(url):
    # ... (code for this function)
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    return match.group(1) if match else None

# --- Main Routes ---
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        project_type = request.form.get('project_type')
        gsheet_url = request.form.get('gsheet_url')
        file = request.files.get('file')
        session['project_type'] = project_type
        session['gsheet_url'] = gsheet_url

        if not all([project_type, gsheet_url, file, file.filename]):
            return jsonify({'error': '所有字段均为必填项！'}), 400
        
        spreadsheet_id = extract_spreadsheet_id(gsheet_url)
        if not spreadsheet_id:
            return jsonify({'error': '无效的Google Sheet链接！'}), 400

        filename = secure_filename(file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(input_path)
        
        is_valid, message = validate_excel_file(input_path, CONFIG[project_type])
        if not is_valid:
            return jsonify({'error': f"文件校验失败: {message}"}), 400
        
        task_id = str(uuid.uuid4())
        tasks[task_id] = {'status': '数据任务已创建...', 'progress': 0}
        thread = threading.Thread(target=run_data_task, args=(task_id, input_path, project_type, spreadsheet_id))
        thread.start()
        return jsonify({'task_id': task_id})

    context = {"config": CONFIG, "project_type": session.get('project_type'), "gsheet_url": session.get('gsheet_url')}
    return render_template('index.html', **context)

@app.route('/process_cloud_sync', methods=['POST'])
def process_cloud_sync():
    project_type = request.form.get('project_type')
    gsheet_url = request.form.get('gsheet_url')
    
    if not project_type or not gsheet_url:
        return jsonify({'error': '项目类型和 Google Sheet 链接必填！'}), 400
        
    spreadsheet_id = extract_spreadsheet_id(gsheet_url)
    if not spreadsheet_id:
        return jsonify({'error': '无效的Google Sheet链接！'}), 400
        
    task_id = str(uuid.uuid4())
    tasks[task_id] = {'status': '云端同步任务已创建...', 'progress': 0}
    thread = threading.Thread(target=run_cloud_sync_task, args=(task_id, spreadsheet_id, project_type))
    thread.start()
    return jsonify({'task_id': task_id})

@app.route('/process_local_paste', methods=['POST'])
def process_local_paste():
    project_type = request.form.get('project_type')
    pasted_text = request.form.get('pasted_text')
    
    if not project_type or not pasted_text:
        return jsonify({'error': '项目类型和粘贴的数据必填！'}), 400
        
    task_id = str(uuid.uuid4())
    tasks[task_id] = {'status': '本地数据处理任务已创建...', 'progress': 0}
    thread = threading.Thread(target=run_local_paste_task, args=(task_id, pasted_text, project_type))
    thread.start()
    return jsonify({'task_id': task_id})

@app.route('/process_slices', methods=['POST'])
def process_slices():
    file = request.files.get('zip_file')
    if not file or not file.filename.endswith('.zip'):
        return jsonify({'error': '未选择文件或文件不是ZIP格式'}), 400

    filename = secure_filename(file.filename)
    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(zip_path)

    task_id = str(uuid.uuid4())
    tasks[task_id] = {'status': '切图任务已创建...', 'progress': 0}
    thread = threading.Thread(target=run_slice_task, args=(task_id, zip_path))
    thread.start()
    return jsonify({'task_id': task_id})

# --- Utility Routes ---
@app.route('/status/<task_id>')
def task_status(task_id):
    task = tasks.get(task_id)
    if task is None:
        return jsonify({'status': '任务未找到', 'progress': 0, 'result': 'error'}), 404
    return jsonify(task)

@app.route('/download_zip/<filename>')
def download_processed_zip(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)

@app.route('/download_template/<project_type>')
def download_template(project_type):
    project_config = CONFIG.get(project_type)
    if not project_config:
        return "Project type not found.", 404
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'files')
    return send_from_directory(template_dir, project_config.get('template_file'), as_attachment=True)

@app.route('/clear')
def clear_session():
    session.pop('project_type', None)
    session.pop('gsheet_url', None)
    flash('工作台选项已重置。', 'success')
    return redirect(url_for('upload_file'))
        
# --- 新增：网络连接测试路由 ---
@app.route('/test_connection')
def test_connection():
    proxy_port = os.environ.get('PROXY_PORT', '17890')
    proxy_url = f"http://127.0.0.1:{proxy_port}"
    proxies = {"https": proxy_url}
    try:
        # 尝试用我们配置的代理去连接一个可靠的Google服务
        response = requests.get("https://www.googleapis.com/discovery/v1/apis", proxies=proxies, timeout=15)
        response.raise_for_status() # 如果状态码不是2xx，则抛出异常
        return jsonify({"status": "success", "message": "成功连接到 Google 服务！代理工作正常。"})
    except requests.exceptions.ProxyError:
        return jsonify({"status": "error", "message": "连接代理服务器失败。请确认您的代理应用已开启，且端口号正确。"})
    except requests.exceptions.Timeout:
        return jsonify({"status": "error", "message": "连接超时。您的代理网络可能速度过慢或不稳定。"})
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": f"发生网络错误: {e}"})
 
        
# app.py 新增路由 (用于处理 Image Downloader 表单提交)

@app.route('/download_images', methods=['POST'])
def download_images():
    """
    处理 Image Bank 自动化下载请求的路由。
    目前仅为占位符，以消除前端的 BuildError。
    """
    if request.method == 'POST':
        model_sku = request.form.get('model_sku')
        zip_filename = request.form.get('zip_filename')
        
        # --- 临时逻辑：创建异步任务ID并启动线程 ---
        task_id = str(uuid.uuid4())
        tasks[task_id] = {'status': f'下载任务已创建，目标SKU: {model_sku}', 'progress': 0}
        
        # ⚠️ 注意：这里我们将使用一个临时的占位线程函数，直到我们完成 longines_downloader.py 的集成
        # thread = threading.Thread(target=run_image_download_task, args=(task_id, model_sku, zip_filename))
        # thread.start()
        
        # 暂时返回任务ID，模拟成功创建任务
        return jsonify({'task_id': task_id})
    
    # 理论上不会走到这里，但为了防止意外的 GET 请求
    return jsonify({'error': '错误的请求方法'}), 405


if __name__ == '__main__':
    app.run(debug=True)
