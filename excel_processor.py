# excel_processor.py (B2C项目通用型号识别版 - 优化版)

import pandas as pd
import re

def clean_product_name(name):
    # (此函数无需修改)
    if not isinstance(name, str): return None, ""
    if re.fullmatch(r'\d{7,}', name.strip()): return None, name.strip()
    non_watch_keywords = ['戒指', '项链', '表带', '珠宝', '吊坠', '耳环', '手链', '手镯', '耳钉', '摆件', '保温杯', '帆布袋', '布袋包', '袋', '包', '雨伞', '香薰', '蜡烛', '礼盒', '配件', '定制']
    is_non_watch_item = any(keyword in name for keyword in non_watch_keywords)
    brands = {"天梭": "Tissot", "美度": "Mido", "汉米尔顿": "Hamilton", "宇联": "Union Glashütte", "帝舵": "Tudor", "雪铁纳": "Certina", "尼维达": "Nivada", "盛时": "PRIME TIME"}
    found_brand = None
    for brand_cn, brand_en in brands.items():
        if brand_cn in name:
            found_brand = brand_cn
            name = name.replace(brand_cn, "").replace(brand_en, "")
            break
    if re.search(r'[\u4e00-\u9fa5]', name):
        name = re.sub(r'[A-Za-z0-9\.-]{5,}', '', name)
        name = re.sub(r'\b[A-Z\s]{2,}\b', '', name)
    name = re.sub(r'\s*\d{1,2}\s*[\*xX]\s*\d{1,2}\s*[A-Za-z]+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', '', name.strip())
    movement_types, movement_found = ["机械", "石英"], None
    for m_type in movement_types:
        if m_type in name:
            movement_found = m_type
            break
    if movement_found and "系列" not in name: name = name.replace(movement_found, "系列" + movement_found)
    if "系列" in name and len(name) > 12: name = name.replace("系列", "")
    if not is_non_watch_item:
        if name.endswith(('男', '女')): name += '表'
        elif name and not name.endswith('表'): name += '腕表'
    return found_brand, name

def process_excel_file(input_path):
    try:
        HUABAN_SHEET_NAME = '活动画板'
        SELECTION_SHEET_NAME = '活动选款'

        print(f"正在从 '{HUABAN_SHEET_NAME}' 的C到F列，第7行开始读取产品型号...")
        df_huaban = pd.read_excel(input_path, sheet_name=HUABAN_SHEET_NAME, skiprows=6, header=None, usecols='C:F')
        
        product_models = []
        
        for index, row in df_huaban.iterrows():
            for item in row:
                if pd.notna(item):
                    model = str(item).strip()
                    
                    # --- 核心修改：全新的、更通用的型号校验逻辑 ---
                    # 1. 长度必须在6到30之间
                    is_length_ok = 6 <= len(model) <= 30
                    # 2. 不能包含中文字符
                    has_no_chinese = not re.search(r'[\u4e00-\u9fa5]', model)
                    # 3. 必须包含至少一个数字
                    has_digit = re.search(r'\d', model)
                    # 4. 只能由字母、数字、点、连字符组成
                    # *** 优化点：添加 re.IGNORECASE 标志，实现不区分大小写的匹配 ***
                    is_valid_chars = re.fullmatch(r'[A-Z0-9\.-]+', model, re.IGNORECASE)                    
                    
                    # 必须同时满足所有条件
                    if is_length_ok and has_no_chinese and has_digit and is_valid_chars:
                        # 关键优化步骤：统一转换为大写格式，直接添加到列表中！
                        product_models.append(model.upper())
        
        if not product_models:
            print(f"错误：在 '{HUABAN_SHEET_NAME}' 的指定区域内，没有找到任何符合格式的产品型号。")
            return pd.DataFrame()
        
        df_models = pd.DataFrame(product_models, columns=['产品型号']).drop_duplicates(keep='first')
        print(f"成功提取到 {len(df_models)} 个不重复的有效产品型号。")
        # --- 修改结束 ---

        # (后续的合并与处理逻辑保持不变)
        df_selection = pd.read_excel(input_path, sheet_name=SELECTION_SHEET_NAME, header=2)
        product_model_column_name = '商品SKU'

        if product_model_column_name not in df_selection.columns:
            print(f"错误: 在 '{SELECTION_SHEET_NAME}' 工作表中找不到关键列 '{product_model_column_name}'。")
            return pd.DataFrame()

        df_models['产品型号'] = df_models['产品型号'].astype(str)
        df_selection[product_model_column_name] = df_selection[product_model_column_name].astype(str)
        merged_df = pd.merge(df_models, df_selection, left_on='产品型号', right_on=product_model_column_name, how='left')
        
        missing_desc_mask = merged_df['表款描述'].isnull()
        merged_df.loc[missing_desc_mask, '表款描述'] = merged_df.loc[missing_desc_mask, '产品型号']
        
        cleaned_data = merged_df['表款描述'].apply(clean_product_name)
        merged_df['品牌名称'], merged_df['表款描述'] = cleaned_data.str[0], cleaned_data.str[1]
        
        column_mapping = {
            '品牌名称': 'brand_name', '商品SKU': 'model_sku', '表款描述': 'product_name', 
            '公价': 'msrp', '销售价': 'sales_price', '券后价': 'final_price'
        }
        
        available_cols = [col for col in column_mapping.keys() if col in merged_df.columns]
        final_df = merged_df[available_cols].rename(columns=column_mapping)
        
        final_df.insert(0, 'sort_order', range(1, 1 + len(final_df)))
        
        return final_df
    except Exception as e:
        import traceback
        print(f"处理B2C文件时发生错误: {e}")
        traceback.print_exc()
        return pd.DataFrame()