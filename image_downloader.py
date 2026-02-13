# image_downloader.py (爬虫流程验证脚本)

import os
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# --- 占位符：请替换为你的真实信息 ---
USERNAME = "sam76826" 
PASSWORD = "zx123456" 
TARGET_MODEL = "L8.124.4.87.2" # 官方认可的带点格式
# --- 占位符结束 ---

BASE_URL = "https://imagebank.longines.com"
# 确保下载路径是明确的，例如在你的D盘项目目录下创建一个临时文件夹
DOWNLOAD_DIR = os.path.join("D:\\Projects\\web_project", "imagebank_downloads") 

def standardize_model(model: str) -> str:
    """标准化型号格式：L+数字+点+数字"""
    # 假设输入的SKU是 L81244872 或 L8.124.4.87.2
    model = model.upper().strip()
    # 如果是无点的长串，尝试添加点
    if re.fullmatch(r'L\d{8,}', model):
        # 简单示例：L81244872 -> L8.124.4.87.2
        return re.sub(r'(L\d{1})(\d{3})(\d{1})(\d{2})(\d{1})', r'\1.\2.\3.\4.\5', model)
    return model

def setup_driver():
    """配置 Chrome WebDriver，设置下载路径"""
    chrome_options = Options()
    # chrome_options.add_argument("--headless") # 跑通流程后再启用无头模式
    
    # 设置自动化下载路径和行为
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False, # 不弹出下载确认框
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True 
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # 假设 ChromeDriver 位于 PATH 或项目目录下
    driver = webdriver.Chrome(options=chrome_options) 
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print(f"✅ WebDriver 配置完成，下载路径: {DOWNLOAD_DIR}")
    return driver

def download_images(driver, model_sku):
    try:
        # 1. 登录
        driver.get(BASE_URL)
        print("➡️ 尝试登录...")
        # 假设登录页面的元素ID/Name/XPath
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "username"))
        ).send_keys(USERNAME)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        # 验证是否登录成功 (等待搜索框出现)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "SearchText"))
        )
        print("🎉 登录成功！")

        # 2. 搜索
        # 标准化型号以确保搜索成功
        search_sku = standardize_model(model_sku)
        print(f"🔍 正在搜索型号: {search_sku}")
        search_box = driver.find_element(By.ID, "SearchText")
        search_box.send_keys(search_sku)
        search_box.submit() # 或点击搜索按钮
        
        # 等待搜索结果加载
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "product-page-container")) # 假设进入了表款页面
        )

        # 3. 选择所有图片
        print("👀 正在查找并选择图片...")
        # 目标文件名后缀，用于精确匹配
        suffixes = ["_BACK", "_DRback", "_DRface", "_FACE", "_SOL"] 
        selected_count = 0

        for suffix in suffixes:
            full_filename_partial = model_sku + suffix
            # 使用 XPath 查找包含特定文件名部分的图片元素
            # 注意：这里的 XPath 需要根据实际网站结构调整
            try:
                # 假设每张图片有一个 Select 按钮/图标
                select_button = driver.find_element(
                    By.XPATH, f"//div[contains(@id, 'file_') and contains(@data-filename, '{full_filename_partial}')]//a[contains(@class, 'select-arrow')]"
                )
                select_button.click()
                selected_count += 1
                time.sleep(0.5) # 稍微等待，模拟用户操作
            except NoSuchElementException:
                print(f"⚠️ 未找到文件: {full_filename_partial}.tif")
                
        if selected_count == 0:
            print("❌ 未成功选择任何图片，流程结束。")
            return False

        # 4. 进入下载页面
        print(f"🛒 已选择 {selected_count} 张图片，进入购物车/手提袋...")
        # 假设手提袋图标的定位器
        cart_button = driver.find_element(By.ID, "cartIcon") 
        cart_button.click()
        
        # 等待下载页面加载
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "downloadButtonContainer")) 
        )

        # 5. 点击 Download JPG
        print("⬇️ 正在点击 'Download JPG' 按钮...")
        download_jpg_button = driver.find_element(By.ID, "downloadJpgButton")
        download_jpg_button.click()
        
        # 6. 下载监控 (简易版：等待一段时间，并检查下载目录)
        print("⏳ 文件下载中，等待 40 秒...")
        time.sleep(40) 
        
        downloaded_files = os.listdir(DOWNLOAD_DIR)
        zip_files = [f for f in downloaded_files if f.endswith('.zip')]
        
        if zip_files:
            print(f"✅ 成功下载文件: {zip_files[0]}")
            return True
        else:
            print("❌ 未在下载目录中找到 ZIP 文件。")
            return False

    except TimeoutException:
        print("❌ 操作超时，可能是网络慢或元素定位器需要更新。")
        return False
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False
    finally:
        driver.quit()
        print("🔌 浏览器已关闭。")

# --- 执行脚本 ---
if __name__ == '__main__':
    driver = setup_driver()
    if download_images(driver, TARGET_MODEL):
        print(f"✨ {TARGET_MODEL} 图片下载流程验证成功！")
    else:
        print(f"🔥 {TARGET_MODEL} 图片下载流程验证失败。")