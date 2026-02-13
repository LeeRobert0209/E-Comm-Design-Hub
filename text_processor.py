import pandas as pd
import io
import re

def parse_pasted_data(text_content):
    """
    解析从 Excel 粘贴的文本数据 (TSV格式)。
    假设第一行是表头。
    """
    if not text_content or not text_content.strip():
        return pd.DataFrame()

    try:
        # 使用 pandas 的 read_csv 读取 tab 分隔符的数据
        df = pd.read_csv(io.StringIO(text_content), sep='\t', dtype=str)
        
        # 清理列名（去除前后空格）
        df.columns = df.columns.str.strip()
        
        # 清理数据（去除前后空格，替换 NaN 为空字符串）
        df = df.fillna('')
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].str.strip()
                
        print(f"成功解析粘贴数据，共 {len(df)} 行，列名: {list(df.columns)}")
        return df
    except Exception as e:
        print(f"解析粘贴数据时出错: {e}")
        return pd.DataFrame()

def process_local_data(df):
    """
    对本地粘贴的数据进行必要的标准化处理。
    例如：确保有 model_sku 列，处理品牌映射等。
    """
    if df.empty:
        return df

    # 1. 尝试识别 SKU 列
    # 常见的 SKU 列名变体
    sku_candidates = ['SKU', '商品SKU', '型号', 'Product Code', 'Model']
    sku_col = None
    for col in df.columns:
        if col in sku_candidates:
            sku_col = col
            break
            
    # 如果没找到标准列名，尝试找第一列看起来像 SKU 的 (包含字母和数字)
    if not sku_col:
        for col in df.columns:
            sample = df[col].iloc[0] if len(df) > 0 else ''
            if re.search(r'[A-Za-z]', str(sample)) and re.search(r'\d', str(sample)):
                sku_col = col
                break
    
    if sku_col:
        print(f"识别到 SKU 列为: '{sku_col}'")
        # 统一重命名为内部使用的 'model_sku'
        df = df.rename(columns={sku_col: 'model_sku'})
    else:
        print("警告: 无法自动识别 SKU 列，后续图片匹配可能失败。请确保粘贴的数据包含 'SKU' 或 '商品SKU' 列。")

    # 2. 新品牌映射逻辑 (占位符)
    # 如果未来需要处理特定的品牌名称转换，可以在这里添加逻辑
    # 例如: df['brand_name'] = df['brand'].map(brand_mapping).fillna(df['brand'])

    return df
