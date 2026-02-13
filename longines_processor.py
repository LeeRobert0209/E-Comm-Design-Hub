import pandas as pd
import re
import math # <<--- 引入 math 库，用于向上取整

def is_title_like(text):
    """
    判断一段文字是否“像”大标题（最严格版本，用于近似“粗体”规则）。
    """
    if not isinstance(text, str) or not text.strip():
        return False
    text = text.strip()
    
    # 规则1: 不能是产品型号
    if re.match(r'L\d', text): return False
    # 规则2: 必须包含中文字符
    if not re.search(r'[\u4e00-\u9fa5]', text): return False
    # 规则3: 排除包含数字、特殊符号的文本 (大标题通常是纯文字的描述性短语)
    if re.search(r'[\d\*\×\%\/\(\)]', text): return False
    # 规则4: 长度限制在20个字符内
    if len(text) > 20: return False 
    # 规则5: 排除一些通用词
    if text.isdigit() or text in ["温馨提示", "品牌故事", "主KV", "部分商品参与满减"]: return False
    return True

def ceil_to_two_decimals(price):
    """
    将价格向上取整到两位小数（商业逻辑：除余结果进一位）。
    例如：608.333... -> 608.34
    """
    if price <= 0:
        return 0.0
    # 核心逻辑：乘以 100，向上取整，再除以 100
    return math.ceil(price * 100) / 100

def process_longines_file(input_path):
    try:
        # 1. 数据加载与预处理
        df_page = pd.read_excel(input_path, sheet_name='画板', header=None, skiprows=2)
        df_sheet = pd.read_excel(input_path, sheet_name='Sheet1')
        df_sheet.columns = df_sheet.columns.str.strip()
        
        # 2. 核心修改1：全局扫描，仅捕获大标题和产品 SKU
        big_titles_loc = []
        products_loc = []

        for r_idx, row in df_page.iterrows():
            non_empty_cells = [str(s).strip() for s in row.dropna() if pd.notna(s) and str(s).strip()]
            
            if not non_empty_cells:
                continue

            # 判断大标题：当这一行只有一个非空单元格，且像标题时
            if len(non_empty_cells) == 1 and is_title_like(non_empty_cells[0]):
                big_titles_loc.append({'title': non_empty_cells[0], 'row': r_idx})
                continue

            # 寻找产品 SKU
            for cell_content in non_empty_cells:
                # 寻找产品型号 (例如 L129194783)
                found_models = re.findall(r'(L\d[A-Z0-9_\.]+)', cell_content)
                if found_models:
                    for model in found_models:
                        products_loc.append({'SKU': model, 'row': r_idx})
        
        # 3. 核心修改2：逻辑关联，为每个产品找到最近的大标题
        products_with_titles = []
        big_titles_rows = {item['row']: item['title'] for item in big_titles_loc}

        for product in products_loc:
            product_row = product['row']
            
            # 查找最近的大标题 (行号 <= product_row 的最大行号)
            last_big_title_rows = [r for r in big_titles_rows if r <= product_row]
            last_big_title = ""
            if last_big_title_rows:
                last_big_title_row = max(last_big_title_rows)
                last_big_title = big_titles_rows[last_big_title_row]
                
            products_with_titles.append({
                'SKU': product['SKU'], 
                'title_b': last_big_title,
            })

        if not products_with_titles:
            return pd.DataFrame()

        # 4. 数据合并与计算
        df_models = pd.DataFrame(products_with_titles).drop_duplicates(subset=['SKU'], keep='first').dropna(subset=['SKU'])
        merged_df = pd.merge(df_models, df_sheet, on='SKU', how='left')
        
        # (提取分期期数)
        merged_df['installments'] = None
        if '分期价' in merged_df.columns:
            extract_pattern = r'\D*(\d+)[期]' 
            extracted_data = merged_df['分期价'].astype(str).str.extract(extract_pattern)
            merged_df['installments'] = pd.to_numeric(extracted_data[0], errors='coerce')

        # 核心修改3：利用 MSRP / 期数 计算分期价并实现向上取整
        
        # 确保 MSRP 是数字类型
        msrp_col = merged_df['建议零售价'].fillna(0) if '建议零售价' in merged_df.columns else 0
        merged_df['msrp'] = pd.to_numeric(msrp_col, errors='coerce').fillna(0)
        
        # 1. 计算原始分期价 (包含无限小数)
        merged_df['installment_price_raw'] = merged_df['msrp'].div(merged_df['installments']).fillna(0)
        
        # 2. 应用向上取整逻辑
        merged_df['installment_price'] = merged_df['installment_price_raw'].apply(ceil_to_two_decimals)
        
        # product_name生成部分（保持不变）
        gender_col = merged_df['性别'].map({'Men': '男款', 'Women': '女款'}).fillna('') if '性别' in merged_df.columns else ""
        movement_col = merged_df['机芯类型'].map({'自动上链机械机芯': '机械', '石英机芯': '石英'}).fillna('') if '机芯类型' in merged_df.columns else ""
        base_name_col = merged_df['二级系列'].fillna('') if '二级系列' in merged_df.columns else merged_df['SKU']
        merged_df['product_name'] = base_name_col + movement_col + gender_col
        merged_df['product_name'] = merged_df['product_name'].str.replace('腕表|码表', '', regex=True)
        
        # 5. 核心修改4：更新最终输出的列并进行格式化
        columns_to_keep = {
            'SKU': 'model_sku', 'product_name': 'product_name', 'msrp': 'msrp',
            'installment_price': 'installment_price', 'installments': 'installments', 
            'title_b': 'title_b'
        }
        
        available_cols = [col for col in columns_to_keep.keys() if col in merged_df.columns]
        final_df = merged_df[available_cols].rename(columns=columns_to_keep)
        
        # 最终格式化：将计算好的浮点数转换为保留两位小数的字符串
        if 'installment_price' in final_df.columns:
            final_df['installment_price'] = final_df['installment_price'].apply(
                # 直接格式化为字符串，x已经是向上取整后的结果
                lambda x: '{:.2f}'.format(x) if x > 0 else ''
            )
        
        final_df.insert(0, 'sort_order', range(1, 1 + len(final_df)))
        
        return final_df
    except Exception as e:
        import traceback
        print(f"An error occurred in process_longines_file: {e}")
        traceback.print_exc()
        return pd.DataFrame()