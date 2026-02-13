import os
import pandas as pd
import socket
import time
import re
import traceback
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError

# (全局设置保持不变)
socket.setdefaulttimeout(300)
PROXY_PORT = "17890" 
os.environ['HTTPS_PROXY'] = f'http://127.0.0.1:{PROXY_PORT}'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/spreadsheets']
PRODUCT_IMG_FOLDER_NAME = "产品图"
SCENE_IMG_FOLDER_NAME = "场景图"

def authenticate_google_drive():
    """
    处理Google Drive的认证流程。
    V2版：增加“自愈”逻辑，在token失效时能自动删除并触发重新认证。
    """
    creds = None
    token_file = 'token.json'

    # 1. 尝试从现有的 token.json 文件加载凭证
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        except Exception as e:
            print(f"⚠️ 读取 {token_file} 文件时出错: {e}。将删除并重新认证。")
            os.remove(token_file)
            creds = None

    # 2. 检查凭证是否有效或已过期
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            print("凭证已过期，正在尝试自动刷新...")
            try:
                creds.refresh(Request())
            # --- 核心修改：捕获刷新失败的特定错误 ---
            except RefreshError as e:
                print(f"⚠️ 自动刷新失败: {e}")
                print(f"检测到授权凭证已失效或被吊销，将自动删除旧的 {token_file} 并重新授权。")
                os.remove(token_file)
                creds = None # 将creds设为None，以触发下面的重新登录流程
            # ----------------------------------------
            except Exception as e:
                print(f"⚠️ 刷新凭证时发生未知错误: {e}")
                os.remove(token_file)
                creds = None
        else:
            # 如果凭证无效且无法刷新
            print(f"⚠️ 无效的凭证文件 {token_file}，将删除并重新授权。")
            os.remove(token_file)
            creds = None

    # 3. 如果经过以上步骤，仍然没有有效的凭证，则启动完整的用户授权流程
    if not creds:
        print("启动新的用户授权流程...")
        # 确保 credentials.json 文件存在
        if not os.path.exists('credentials.json'):
             print("🚨 错误: 找不到 'credentials.json' 文件，无法进行用户授权。")
             return None
             
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        # 将新凭证保存到 token.json 供下次使用
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
            print(f"🎉 新的授权凭证已成功保存到 {token_file}。")

    return creds

def execute_with_retry(api_call):
    for attempt in range(3):
        try:
            return api_call.execute()
        except HttpError as e:
            if e.resp.status in [429, 500, 502, 503, 504]:
                print(f"⚠️ API请求失败 (状态码: {e.resp.status})，将在5秒后重试 (第 {attempt + 1}/3 次)...")
                time.sleep(5)
            else: raise e
        except Exception as e:
            print(f"⚠️ 发生网络连接错误 ({type(e).__name__})，将在5秒后重试 (第 {attempt + 1}/3 次)...")
            time.sleep(5)
    raise Exception("API请求在重试3次后仍然失败。")

def get_folder_id(service, folder_name, parent_id=None):
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}'"
    if parent_id: query += f" and '{parent_id}' in parents"
    response = execute_with_retry(service.files().list(q=query, fields='files(id, name)'))
    files = response.get('files', [])
    return files[0]['id'] if files else None

def get_all_files_in_folder(service, folder_id):
    """
    获取文件夹中所有文件的ID和名称，并将名称统一转换为大写作为Map的Key。
    以解决大小写敏感的文件匹配问题。
    """
    file_map, page_token = {}, None
    while True:
        response = execute_with_retry(service.files().list(q=f"'{folder_id}' in parents", fields='nextPageToken, files(id, name)', pageToken=page_token))
        for file in response.get('files', []):
            # *** 关键修改：将文件名（作为key）统一转换为大写，以实现大小写不敏感查找 ***
            filename_no_ext = os.path.splitext(file.get('name'))[0].upper() 
            file_map[filename_no_ext] = file.get('id')
        page_token = response.get('nextPageToken', None)
        if page_token is None: break
    return file_map

def find_image_links_for_df(df: pd.DataFrame, project_config: dict, creds):
    if df is None or df.empty: return df
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        PARENT_FOLDER_NAME = project_config['drive_folder']
        print(f"项目: '{project_config['display_name']}', 正在查找主文件夹 '{PARENT_FOLDER_NAME}'...")
        parent_folder_id = get_folder_id(drive_service, PARENT_FOLDER_NAME)
        if not parent_folder_id: return df
        
        # *** 安全保障：确保用于查找的SKU在当前函数中也是大写 ***
        df['model_sku'] = df['model_sku'].astype(str).str.upper() 

        print(f"正在查找子文件夹 '{PRODUCT_IMG_FOLDER_NAME}' 和 '{SCENE_IMG_FOLDER_NAME}'...")
        product_folder_id = get_folder_id(drive_service, PRODUCT_IMG_FOLDER_NAME, parent_folder_id)
        scene_folder_id = get_folder_id(drive_service, SCENE_IMG_FOLDER_NAME, parent_folder_id)
        if not (product_folder_id and scene_folder_id): return df
        print("正在缓存文件夹中的所有文件名...")
        
        # 此时，product_file_map 和 scene_file_map 中的 keys 都是大写文件名
        product_file_map = get_all_files_in_folder(drive_service, product_folder_id)
        scene_file_map = get_all_files_in_folder(drive_service, scene_folder_id)
        
        print("文件名缓存完成！")
        
        def search_link(model_number, file_map):
            # model_number 保证是大写的，file_map 的 key 也是大写的
            if not model_number: return ""
            
            # 1. 优先进行精确匹配 (model_number == 文件名, 例如 H11221851)
            if model_number in file_map:
                file_id = file_map[model_number]
                return f"https://lh3.googleusercontent.com/d/{file_id}=s0"
                
            # 2. 回退到子串匹配，用于查找带有后缀的文件名（例如：H11221851_DETAIL）
            for file_name_upper, file_id in file_map.items():
                if model_number in file_name_upper: 
                    return f"https://lh3.googleusercontent.com/d/{file_id}=s0"
            return ""

        print("开始为每一行数据匹配图片链接...")
        # 由于 df['model_sku'] 已经是大写，这里调用 search_link 就能实现大小写不敏感查找
        df['product_image'] = df['model_sku'].apply(lambda x: search_link(x, product_file_map))
        df['scene_image'] = df['model_sku'].apply(lambda x: search_link(x, scene_file_map))
        print("图片链接匹配完成！")
        return df
    except Exception:
        print("查找Google Drive图片时发生严重错误:")
        traceback.print_exc()
        return df # 返回原始df而不是None，以防后续流程崩溃

def update_google_sheet(spreadsheet_id, df: pd.DataFrame, creds):
    try:
        print("正在连接 Google Sheets API...")
        service = build('sheets', 'v4', credentials=creds)
        sheet_api = service.spreadsheets()
        sheet_metadata = execute_with_retry(sheet_api.get(spreadsheetId=spreadsheet_id))
        first_sheet_name = sheet_metadata.get('sheets', [{}])[0].get('properties', {}).get('title', 'Sheet1')
        print(f"检测到目标工作表名称为: '{first_sheet_name}'")
        df_cleaned = df.fillna('')
        values = [df_cleaned.columns.values.tolist()] + df_cleaned.values.tolist()
        print(f"正在清空目标表格 '{first_sheet_name}' (这可能需要几分钟，请耐心等待)...")
        execute_with_retry(sheet_api.values().clear(spreadsheetId=spreadsheet_id, range=first_sheet_name))
        print("正在写入新数据...")
        body = {'values': values}
        execute_with_retry(sheet_api.values().update(spreadsheetId=spreadsheet_id, range=f'{first_sheet_name}!A1', valueInputOption='USER_ENTERED', body=body))
        print("🎉 成功将数据更新到Google Sheet！")
        return True
    except Exception:
        print(f"更新Google Sheet时发生严重错误:")
        traceback.print_exc()
        return False

def read_sheet_data(spreadsheet_id, creds, range_name=None):
    """
    读取Google Sheet数据并转换为DataFrame。
    用于【模式A：云端实时回填】功能。
    """
    try:
        print(f"正在连接 Google Sheets API 以读取数据 ({spreadsheet_id})...", flush=True)
        service = build('sheets', 'v4', credentials=creds)
        sheet_api = service.spreadsheets()
        
        # 0. 如果没有指定 range_name，自动获取第一个 Sheet 的名字
        if not range_name:
            print("正在获取工作表名称...", flush=True)
            sheet_metadata = execute_with_retry(sheet_api.get(spreadsheetId=spreadsheet_id))
            sheets = sheet_metadata.get('sheets', [])
            if not sheets:
                raise ValueError("未找到任何工作表")
            range_name = sheets[0].get('properties', {}).get('title', 'Sheet1')
            print(f"检测到目标工作表名称为: '{range_name}'", flush=True)

        # 1. 获取 Sheet 数据
        print(f"正在读取数据范围: {range_name}...", flush=True)
        result = execute_with_retry(sheet_api.values().get(spreadsheetId=spreadsheet_id, range=range_name))
        values = result.get('values', [])
        
        if not values:
            print('No data found.', flush=True)
            return pd.DataFrame()

        # 2. 转换为 DataFrame
        # 假设第一行是表头
        header = values[0]
        data = values[1:]
        
        # 处理数据列数不一致的问题（补齐空值）
        if header:
            max_cols = len(header)
            data_fixed = []
            for row in data:
                # 如果行比表头短，补齐
                if len(row) < max_cols:
                    row.extend([''] * (max_cols - len(row)))
                # 如果行比表头长，截断（虽然这种情况少见）
                data_fixed.append(row[:max_cols])
                
            df = pd.DataFrame(data_fixed, columns=header)
        else:
            df = pd.DataFrame(data)

        print(f"成功读取 {len(df)} 行数据。", flush=True)
        return df

    except Exception as e:
        print(f"读取Google Sheet时发生错误: {e}", flush=True)
        traceback.print_exc()
        return pd.DataFrame()
