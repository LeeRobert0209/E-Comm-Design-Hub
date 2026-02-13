// static/js/main.js (V7 - 修复作用域和轮询逻辑的完整代码)

// --- 1. 全局函数：Tab 切换, Template Link, Upload Area (保持不变) ---

function openTab(evt, tabName) {
    let i, tabcontent, tablinks;
    tabcontent = document.getElementsByClassName("tab-content");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    tablinks = document.getElementsByClassName("tab-link");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
    }
    document.getElementById(tabName).style.display = "block";
    evt.currentTarget.className += " active";
}

function openSubTab(evt, subTabName) {
    let i, subtabcontent, subtablinks;
    subtabcontent = document.getElementsByClassName("sub-tab-content");
    for (i = 0; i < subtabcontent.length; i++) {
        subtabcontent[i].style.display = "none";
    }
    subtablinks = document.getElementsByClassName("sub-tab-link");
    for (i = 0; i < subtablinks.length; i++) {
        subtablinks[i].className = subtablinks[i].className.replace(" active", "");
    }
    document.getElementById(subTabName).style.display = "block";
    evt.currentTarget.className += " active";
}

function updateTemplateLink() {
    const projectTypeSelect = document.getElementById('project-type');
    const downloadArea = document.getElementById('template-download-area');
    if (projectTypeSelect && projectTypeSelect.value) {
        const templateLink = document.getElementById('template-link');
        templateLink.href = `/download_template/${projectTypeSelect.value}`;
        downloadArea.style.display = 'block';
    } else if (downloadArea) {
        downloadArea.style.display = 'none';
    }
}

function setupUploadArea(dropZoneId, fileInputId, fileNameId) {
    const dropZone = document.getElementById(dropZoneId);
    const fileInput = document.getElementById(fileInputId);
    const fileNameDisplay = document.getElementById(fileNameId);
    if (!dropZone || !fileInput || !fileNameDisplay) return;

    const updateFileName = () => {
        if (fileInput.files.length > 0) {
            fileNameDisplay.textContent = `已选择文件: ${fileInput.files[0].name}`;
        } else {
            fileNameDisplay.textContent = "";
        }
    };

    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', updateFileName);
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone.addEventListener('dragleave', () => { dropZone.classList.remove('drag-over'); });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            updateFileName();
        }
    });
}

// --- 2. 轮询状态函数：提升到全局作用域 (修复了 'is not defined' 错误) ---

/**
 * 启动任务状态轮询。
 */
function startPolling(taskId, statusUrlBase, progressBar, progressStatus, submitButton) {
    const url = statusUrlBase.replace('_TASK_ID_', taskId);
    let pollingInterval; // 使用局部变量存储 Interval ID

    // 定义任务结束处理函数
    const handleTaskEnd = (isSuccess, message, downloadUrl = null) => {
        const originalButtonText = submitButton.closest('form').id === 'data-form' ? '开始处理并更新' : '开始处理并下载';
        submitButton.disabled = false;
        submitButton.textContent = isSuccess ? '完成' : '重试';

        // 确保清除之前的 Interval
        if (pollingInterval) clearInterval(pollingInterval);

        if (isSuccess) {
            progressBar.style.backgroundColor = '#4CAF50'; // 绿色
            progressStatus.className = 'success';

            if (downloadUrl) {
                progressStatus.innerHTML = `任务完成！<a href="${downloadUrl}" class="download-link" target="_blank">点击下载文件</a>`;
            } else {
                progressStatus.textContent = message || '任务完成！数据已成功更新。';
            }
        } else {
            progressBar.style.backgroundColor = '#f44336'; // 红色
            progressStatus.className = 'error';
            progressStatus.textContent = message;
        }
    };

    // 启动轮询
    pollingInterval = setInterval(function () {
        fetch(url)
            .then(response => response.json())
            .then(data => {
                const progress = data.progress || 0;
                const status = data.status || '正在处理...';
                const result = data.result;

                progressBar.style.width = progress + '%';
                progressStatus.textContent = status;

                // 重置进度条颜色为默认（处理中）
                if (result !== 'success' && result !== 'error') {
                    progressBar.style.backgroundColor = '#2196F3'; // 蓝色
                }


                if (result === 'success' || result === 'error') {
                    // 停止轮询，调用结束处理
                    handleTaskEnd(result === 'success', status, data.download_url);
                }
            })
            .catch(error => {
                // 轮询失败（网络连接问题等）
                handleTaskEnd(false, '轮询失败: ' + error.message);
            });
    }, 2000); // 每2秒查询一次状态
}


// --- 3. 任务表单通用设置 (微调，移除了内部的 startPolling) ---

function setupTaskForm(formId, progressAreaId, progressStatusId, progressBarId) {
    const form = document.getElementById(formId);
    if (!form) return;

    const fieldset = form.querySelector('fieldset');
    const submitButton = form.querySelector('button[type="submit"]');
    const progressArea = document.getElementById(progressAreaId);
    const progressStatus = document.getElementById(progressStatusId);
    const progressBar = document.getElementById(progressBarId);

    // 获取 formId 来确定按钮的原始文本
    const originalButtonText = formId === 'data-form' ? '开始处理并更新' : '开始处理并下载';

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        const formData = new FormData(form);
        const uploadUrl = form.dataset.uploadUrl;
        const statusUrlBase = form.dataset.statusUrlBase; // 现在从这里获取

        fieldset.disabled = true;
        submitButton.textContent = '处理中...';
        progressArea.style.display = 'block';
        progressStatus.className = '';
        progressStatus.textContent = '正在上传文件...';
        progressBar.className = 'progress-bar';
        progressBar.style.width = '5%';
        progressBar.style.backgroundColor = '#2196F3'; // 默认蓝色

        fetch(uploadUrl, { method: 'POST', body: formData })
            .then(response => {
                if (!response.ok) { throw new Error(`HTTP 错误: ${response.status}`); }
                return response.json();
            })
            .then(data => {
                if (data.error) { throw new Error(data.error); }

                // 调用全局的 startPolling，并传入所有需要的参数
                startPolling(data.task_id, statusUrlBase, progressBar, progressStatus, submitButton);
            })
            .catch(error => {
                // 任务提交失败的统一处理
                submitButton.textContent = originalButtonText;
                submitButton.disabled = false;
                progressStatus.className = 'error';
                progressStatus.textContent = `任务提交失败: ${error.message}`;
                progressBar.style.backgroundColor = '#f44336';
            });
    });
}


// --- 4. DOMContentLoaded 初始化逻辑 (更新为使用通用函数) ---

document.addEventListener('DOMContentLoaded', function () {
    // 默认打开第一个 Tab
    openTab({ currentTarget: document.querySelector('.tab-link.active') }, 'data-processor');

    // --- 统一初始化所有任务表单 ---
    setupTaskForm('data-form', 'progress-area', 'progress-status', 'progress-bar');
    setupTaskForm('cloud-sync-form', 'cloud-progress-area', 'cloud-progress-status', 'cloud-progress-bar');
    setupTaskForm('local-paste-form', 'paste-progress-area', 'paste-progress-status', 'paste-progress-bar');
    setupTaskForm('slice-form', 'slice-progress-area', 'slice-progress-status', 'slice-progress-bar');
    // 【重要】素材下载器现在也使用通用的 setupTaskForm 来初始化！
    setupTaskForm('image-download-form', 'image-download-progress-area', 'image-download-progress-status', 'image-download-progress-bar');


    updateTemplateLink();
    const projectTypeSelect = document.getElementById('project-type');
    if (projectTypeSelect) {
        projectTypeSelect.addEventListener('change', updateTemplateLink);
    }

    setupUploadArea('excel-drop-zone', 'excel-file-input', 'excel-file-name');
    setupUploadArea('zip-drop-zone', 'zip-file-input', 'zip-file-name');

    // --- 网络测试按钮的逻辑 (不变) ---
    const testBtn = document.getElementById('test-connection-btn');
    if (testBtn) {
        testBtn.addEventListener('click', function () {
            const originalText = testBtn.textContent;
            testBtn.textContent = '测试中...';
            testBtn.disabled = true;

            fetch(testBtn.dataset.url) // 从data-url属性获取链接
                .then(response => response.json())
                .then(data => {
                    alert(`网络测试结果:\n\n状态: ${data.status.toUpperCase()}\n消息: ${data.message}`);
                    testBtn.textContent = originalText;
                    testBtn.disabled = false;
                })
                .catch(error => {
                    alert(`网络测试失败: 无法连接到工作台后台。错误: ${error}`);
                    testBtn.textContent = originalText;
                    testBtn.disabled = false;
                });
        });
    }
});