# slice_processor.py

import os
import re
from PIL import Image
from io import BytesIO

TARGET_SIZE = 150 * 1024
SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png')
TARGET_WIDTH = 750  # 新增：目标宽度像素

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def resize_image(img, image_path):
    """
    调整图片宽度：
    1. 如果宽度 > TARGET_WIDTH (750px)，则等比缩放到 TARGET_WIDTH。
    2. 如果宽度 < TARGET_WIDTH (750px) 且宽度 > 375px，则等比拉宽到 TARGET_WIDTH。
    3. 如果宽度 <= 375px，则不调整尺寸。
    """
    original_width, original_height = img.size
    new_img = img

    # 情况1: 宽度 > TARGET_WIDTH (750px)，等比缩放
    if original_width > TARGET_WIDTH:
        new_height = int(original_height * TARGET_WIDTH / original_width)
        new_img = img.resize((TARGET_WIDTH, new_height), Image.Resampling.LANCZOS)
        print(f"📐 缩放宽度: {original_width}px -> {TARGET_WIDTH}px")
    
    # 情况2: 宽度 < TARGET_WIDTH (750px) 且 > 375px，等比拉宽
    elif original_width < TARGET_WIDTH and original_width > 375:
        new_height = int(original_height * TARGET_WIDTH / original_width)
        # 注意：拉伸可能会损失画质，但这里用 Image.Resampling.LANCZOS (高质量滤波)
        new_img = img.resize((TARGET_WIDTH, new_height), Image.Resampling.LANCZOS)
        print(f"📏 拉伸宽度: {original_width}px -> {TARGET_WIDTH}px")

    # 情况3: 宽度 <= 375px，不调整

    return new_img

def compress_image(image_path):
    try:
        original_size = os.path.getsize(image_path)
        img = Image.open(image_path)

        # --- 新增尺寸调整步骤 ---
        img = resize_image(img, image_path)
        # --- 尺寸调整结束 ---

        # 确保RGBA的PNG图在保存为JPG时不会出错
        if img.mode == 'RGBA' and image_path.lower().endswith(('.jpg', '.jpeg')):
            img = img.convert('RGB')

        # 检查调整尺寸后的图片大小，如果已经满足，则保存并返回
        # 注意：这里需要先保存一次，因为调整尺寸可能会改变大小。
        # 为了避免文件I/O，我们先尝试用最高质量保存到内存检查大小。
        temp_buffer = BytesIO()
        img_format = img.format if img.format else 'JPEG'
        
        # 尝试以高画质保存，检查是否已在目标范围内
        save_kwargs_initial = {"format": img_format, "optimize": True}
        if img_format.upper() in ["JPEG", "JPG"]:
            save_kwargs_initial["quality"] = 95 # 用一个较高的初始质量来检查

        img.save(temp_buffer, **save_kwargs_initial)
        current_size = temp_buffer.tell()

        if current_size <= TARGET_SIZE:
            # 如果高画质保存后就在目标内，则直接覆盖原文件
            with open(image_path, "wb") as f:
                f.write(temp_buffer.getvalue())
            print(f"✅ 尺寸调整后，文件大小已在目标范围内：{os.path.basename(image_path)}")
            return True
        
        # 如果尺寸调整后仍然超标，则开始压缩循环
        quality, step = 85, 5
        while quality >= 10:
            buffer = BytesIO()
            save_kwargs = {"format": img_format, "optimize": True}
            if img_format.upper() in ["JPEG", "JPG"]:
                save_kwargs["quality"] = quality

            # 对于PNG，可以使用更激进的优化/压缩级别，但PIL的save方法主要是靠`optimize`和`compress_level`
            # 对于PNG我们不使用quality参数，而是让PIL自行优化
            if img_format.upper() == "PNG":
                # 尝试通过降采样或降低色彩深度来进一步减少大小，这里仅靠PIL的默认优化
                # 如果是PNG，压缩主要靠无损压缩级别 (compress_level)，这里先保持默认
                if quality == 85: # 仅在第一次循环尝试设置较高的compress_level
                     save_kwargs["compress_level"] = 9 
                pass 
            
            img.save(buffer, **save_kwargs)
            current_size_compressed = buffer.tell()

            if current_size_compressed <= TARGET_SIZE:
                with open(image_path, "wb") as f:
                    f.write(buffer.getvalue())
                print(f"🗜️ 成功压缩：{os.path.basename(image_path)} => {current_size_compressed // 1024}KB")
                return True
            else:
                quality -= step
                # 如果是PNG，压缩循环效果不明显，可以考虑跳出，避免无限循环
                if img_format.upper() == "PNG" and quality <= 70 and quality % 10 != 0 : 
                    # PNG的quality下降对文件大小影响小，除非转换格式或降采样，这里简单地减少迭代
                    quality = 10 

        print(f"❌ 无法压缩至{TARGET_SIZE // 1024}KB以下：{os.path.basename(image_path)}")
        return False
        
    except Exception as e:
        print(f"⚠️ 错误处理图片 {os.path.basename(image_path)}：{e}")
        return False

# 以下函数保持不变
def rename_images_in_folder(folder_path):
    images = []
    for file in os.listdir(folder_path):
        if file.lower().endswith(SUPPORTED_EXTENSIONS):
            images.append(file)

    images.sort(key=natural_sort_key)

    temp_files = []
    # 先重命名为临时名字，防止冲突
    for index, old_file in enumerate(images):
        old_path = os.path.join(folder_path, old_file)
        extension = os.path.splitext(old_file)[1].lower()
        temp_name = f"__temp_{index}{extension}"
        temp_path = os.path.join(folder_path, temp_name)
        os.rename(old_path, temp_path)
        temp_files.append((temp_path, extension))

    # 再从临时名字重命名为最终数字名字
    for index, (temp_path, extension) in enumerate(temp_files, start=1):
        new_path = os.path.join(folder_path, f"{index}{extension}")
        os.rename(temp_path, new_path)
        print(f"🔄 重命名: {os.path.basename(temp_path)} -> {index}{extension}")

def compress_images_in_folder(folder_path):
    for file in os.listdir(folder_path):
        if file.lower().endswith(SUPPORTED_EXTENSIONS):
            # 注意：这里我们是直接在原文件上操作的，不需要返回值
            compress_image(os.path.join(folder_path, file))

def process_slice_folder(folder_path):
    """对指定文件夹执行重命名和压缩的核心函数"""
    print("---")
    print("🔄 开始重命名图片...")
    rename_images_in_folder(folder_path)
    print("---")
    print("🗜️ 开始调整尺寸和压缩图片...")
    compress_images_in_folder(folder_path)
    print("---")
    print("🎉 所有图片处理完成！")
    return True