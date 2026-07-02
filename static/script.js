document.addEventListener('DOMContentLoaded', () => {
    // ===== BUSCAR VERSÃO =====
    function loadAppVersion() {
        const badge = document.getElementById('app-version-badge');
        if (!badge) return;
        fetch(window.location.origin + '/api/version')
            .then(res => res.json())
            .then(data => {
                if (data.version) {
                    badge.textContent = `v${data.version}`;
                }
            })
            .catch(err => {
                console.error("Erro ao buscar versão da API:", err);
                badge.textContent = 'v1.5.0'; // Fallback
            });
    }
    loadAppVersion();

    // ===== ELEMENTOS =====
    const form = document.getElementById('summary-form');
    const urlInput = document.getElementById('url-input');
    const detailSelect = document.getElementById('detailLevel');
    const langSelect = document.getElementById('language');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = document.querySelector('.btn-text');
    const loader = document.querySelector('.loader');

    // Resultados
    const resultSection = document.getElementById('result-section');
    const typeBadge = document.getElementById('content-type-badge');
    const resultTitle = document.getElementById('result-title');
    const summaryText = document.getElementById('summary-text');
    const keyPointsList = document.getElementById('key-points-list');
    const warningsContainer = document.getElementById('warnings-container');
    const resetBtn = document.getElementById('reset-btn');

    // Structured & Plain blocks
    const structuredResultBlock = document.getElementById('structured-result-block');
    const plainTextResultBlock = document.getElementById('plain-text-result-block');
    const plainTextContent = document.getElementById('plain-text-content');

    // Sidebar & Overlay
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const openSidebarBtn = document.getElementById('openSidebar');
    const closeSidebarBtn = document.getElementById('closeSidebar');

    // Configurações de IA
    const apiProviderSelect = document.getElementById('api-provider-select');
    const apiKeyInput = document.getElementById('api-key-input');
    const modelInput = document.getElementById('model-input');
    const modelDatalist = document.getElementById('model-datalist');
    const fetchModelsBtn = document.getElementById('fetch-models-btn');
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    
    // Upload de Cookies
    const cookieFileInput = document.getElementById('cookie-file-input');
    const uploadCookiesBtn = document.getElementById('upload-cookies-btn');
    const cookieUploadStatus = document.getElementById('cookie-upload-status');

    // Gerenciador de Diretrizes
    const promptListContainer = document.getElementById('promptListContainer');
    const createNewPromptBtn = document.getElementById('createNewPromptBtn');
    const exportPromptsBtn = document.getElementById('exportPromptsBtn');
    const importPromptsBtn = document.getElementById('importPromptsBtn');
    const importFileInput = document.getElementById('importFileInput');

    // Editor de Prompt
    const promptEditorCard = document.getElementById('promptEditorCard');
    const editorTitle = document.getElementById('editorTitle');
    const editorPromptName = document.getElementById('editorPromptName');
    const editorPromptText = document.getElementById('editorPromptText');
    const editorIncludeJson = document.getElementById('editorIncludeJson');
    const cancelEditorBtn = document.getElementById('cancelEditorBtn');
    const saveEditorBtn = document.getElementById('saveEditorBtn');

    // Live Preview
    const livePreviewContainer = document.getElementById('livePreviewContainer');
    const livePreviewText = document.getElementById('livePreviewText');
    const togglePreviewTextBtn = document.getElementById('togglePreviewTextBtn');
    const activePromptBadge = document.getElementById('activePromptBadge');

    // ===== CONSTANTES PROMPT PADRÃO =====
    const DEFAULT_PROMPT_TEXT = "Você é um analisador de conteúdo de redes sociais. Resuma o conteúdo com fidelidade, sem inventar informações. Quando a transcrição parecer incompleta, avise claramente.";
    const JSON_REQUIREMENT_TEXT = "\n\nRetorne sua resposta estritamente no formato JSON, contendo as chaves: 'summary' (string), 'key_points' (lista de strings), 'possible_title' (string) e 'content_type' (string, como 'notícia', 'dica', 'humor', etc).";

    // ===== ESTADO =====
    let customPrompts = [];
    let defaultPromptOverride = {
        text: DEFAULT_PROMPT_TEXT,
        includeJson: true
    };
    let selectedPromptId = 'default'; // 'default' ou número do index
    let editingIndex = null; // null = criando novo, 'default' = editando padrão, número = editando custom

    // ===== CARREGAR CONFIGURAÇÕES =====
    const loadSettings = async () => {
        // Tentar carregar credenciais do backend primeiro
        try {
            const resp = await fetch(window.location.origin + '/api/settings');
            if (resp.ok) {
                const settings = await resp.json();
                if (settings.api_key) apiKeyInput.value = settings.api_key;
                if (settings.api_url) apiProviderSelect.value = settings.api_url;
                if (settings.model) modelInput.value = settings.model;
            }
        } catch (e) {
            console.warn("Não foi possível carregar configurações do backend, usando localStorage como fallback.", e);
            // Fallback para localStorage
            const savedProvider = localStorage.getItem('socialTxt_apiProvider');
            const savedKey = localStorage.getItem('socialTxt_apiKey');
            const savedModel = localStorage.getItem('socialTxt_model');

            if (savedProvider) apiProviderSelect.value = savedProvider;
            if (savedKey) apiKeyInput.value = savedKey;
            if (savedModel) modelInput.value = savedModel;
        }

        // Custom Prompts
        const savedPrompts = localStorage.getItem('socialTxt_customPrompts_v2');
        if (savedPrompts) {
            try {
                customPrompts = JSON.parse(savedPrompts);
            } catch(e) {
                customPrompts = [];
            }
        } else {
            // Migrar da versão 1 antiga se existir
            const savedPromptsV1 = localStorage.getItem('socialTxt_customPrompts');
            if (savedPromptsV1) {
                try {
                    const parsed = JSON.parse(savedPromptsV1);
                    customPrompts = parsed.map(p => ({
                        name: p.name,
                        text: p.text,
                        includeJson: true
                    }));
                    localStorage.setItem('socialTxt_customPrompts_v2', JSON.stringify(customPrompts));
                } catch(e) {
                    customPrompts = [];
                }
            }
        }

        // Default Prompt Override
        const savedDefaultOverride = localStorage.getItem('socialTxt_defaultPromptOverride');
        if (savedDefaultOverride) {
            try {
                defaultPromptOverride = JSON.parse(savedDefaultOverride);
            } catch(e) {
                defaultPromptOverride = { text: DEFAULT_PROMPT_TEXT, includeJson: true };
            }
        }

        // Selected prompt ID
        const savedSelectedPromptId = localStorage.getItem('socialTxt_selectedPromptId');
        if (savedSelectedPromptId !== null) {
            selectedPromptId = savedSelectedPromptId;
        }

        renderPromptList();
        updateLivePreview();
    };

    // ===== SALVAR PROMPTS =====
    const savePrompts = () => {
        localStorage.setItem('socialTxt_customPrompts_v2', JSON.stringify(customPrompts));
        localStorage.setItem('socialTxt_defaultPromptOverride', JSON.stringify(defaultPromptOverride));
        localStorage.setItem('socialTxt_selectedPromptId', selectedPromptId);
        updateLivePreview();
        updateActivePromptBadge();
    };

    // ===== ATUALIZAR ACTIVE BADGE =====
    const updateActivePromptBadge = () => {
        if (selectedPromptId === 'default') {
            activePromptBadge.textContent = '📋 Padrão';
        } else {
            const idx = parseInt(selectedPromptId);
            if (customPrompts[idx]) {
                activePromptBadge.textContent = '📋 ' + customPrompts[idx].name;
            } else {
                activePromptBadge.textContent = '📋 Padrão';
                selectedPromptId = 'default';
            }
        }
    };

    // ===== ATUALIZAR LIVE PREVIEW =====
    const updateLivePreview = () => {
        let activeText = "";
        let includeJson = true;

        if (selectedPromptId === 'default') {
            activeText = defaultPromptOverride.text;
            includeJson = defaultPromptOverride.includeJson;
        } else {
            const idx = parseInt(selectedPromptId);
            if (customPrompts[idx]) {
                activeText = customPrompts[idx].text;
                includeJson = customPrompts[idx].includeJson;
            } else {
                activeText = defaultPromptOverride.text;
                includeJson = defaultPromptOverride.includeJson;
            }
        }

        const finalPrompt = activeText + (includeJson ? JSON_REQUIREMENT_TEXT : "");
        livePreviewText.textContent = finalPrompt;
    };

    // ===== RENDERIZAR LISTA DE PROMPTS =====
    const renderPromptList = () => {
        promptListContainer.innerHTML = '';

        // 1. Renderizar o Prompt Padrão (Sem drag & drop)
        const isDefaultActive = (selectedPromptId === 'default');
        const defaultCard = document.createElement('div');
        defaultCard.className = `prompt-card ${isDefaultActive ? 'active' : ''}`;
        defaultCard.setAttribute('data-id', 'default');
        
        // Determinar se o padrão foi modificado
        const isDefaultModified = defaultPromptOverride.text !== DEFAULT_PROMPT_TEXT || !defaultPromptOverride.includeJson;

        defaultCard.innerHTML = `
            <div class="prompt-card-status"></div>
            <div class="prompt-card-title">📌 Padrão ${isDefaultModified ? '<span class="hint">(Modificado)</span>' : ''}</div>
            <div class="prompt-card-actions">
                <button type="button" class="prompt-card-btn edit-btn" title="Editar diretriz padrão">✏️</button>
                ${isDefaultModified ? `<button type="button" class="prompt-card-btn reset-btn-card" title="Resetar diretriz padrão para original">🔄</button>` : ''}
            </div>
        `;

        // Eventos card padrão
        defaultCard.addEventListener('click', (e) => {
            if (e.target.closest('.edit-btn')) {
                openEditor('default');
                return;
            }
            if (e.target.closest('.reset-btn-card')) {
                resetDefaultPrompt();
                return;
            }
            selectedPromptId = 'default';
            savePrompts();
            renderPromptList();
        });

        promptListContainer.appendChild(defaultCard);

        // 2. Renderizar Custom Prompts (Com suporte a drag & drop)
        customPrompts.forEach((p, idx) => {
            const isActive = (selectedPromptId === idx.toString());
            const card = document.createElement('div');
            card.className = `prompt-card ${isActive ? 'active' : ''}`;
            card.setAttribute('draggable', 'true');
            card.setAttribute('data-index', idx);

            card.innerHTML = `
                <div class="prompt-drag-handle" title="Arraste para reordenar">☰</div>
                <div class="prompt-card-status"></div>
                <div class="prompt-card-title" title="${p.name}">${p.name}</div>
                <div class="prompt-card-actions">
                    <button type="button" class="prompt-card-btn duplicate-btn" title="Duplicar">👯</button>
                    <button type="button" class="prompt-card-btn edit-btn" title="Editar">✏️</button>
                    <button type="button" class="prompt-card-btn delete-btn delete" title="Excluir">🗑️</button>
                </div>
            `;

            // Eventos do card
            card.addEventListener('click', (e) => {
                if (e.target.closest('.prompt-drag-handle')) return; // ignorar cliques no drag handle
                
                if (e.target.closest('.edit-btn')) {
                    openEditor(idx);
                    return;
                }
                if (e.target.closest('.duplicate-btn')) {
                    duplicatePrompt(idx);
                    return;
                }
                if (e.target.closest('.delete-btn')) {
                    deletePrompt(idx);
                    return;
                }
                selectedPromptId = idx.toString();
                savePrompts();
                renderPromptList();
            });

            // Adicionar handlers do Drag and Drop
            setupDragAndDropHandlers(card);

            promptListContainer.appendChild(card);
        });
    };

    // ===== DRAG AND DROP LOGIC =====
    let draggedIndex = null;

    const setupDragAndDropHandlers = (card) => {
        card.addEventListener('dragstart', (e) => {
            draggedIndex = parseInt(card.getAttribute('data-index'));
            card.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', draggedIndex);
        });

        card.addEventListener('dragover', (e) => {
            e.preventDefault();
            const overCard = e.target.closest('.prompt-card');
            if (!overCard || overCard.getAttribute('data-id') === 'default') return;

            const overIndex = parseInt(overCard.getAttribute('data-index'));
            if (draggedIndex !== null && overIndex !== draggedIndex) {
                // Move item in array dynamically
                const item = customPrompts.splice(draggedIndex, 1)[0];
                customPrompts.splice(overIndex, 0, item);
                
                // Update selected ID if needed
                if (selectedPromptId === draggedIndex.toString()) {
                    selectedPromptId = overIndex.toString();
                } else if (selectedPromptId === overIndex.toString()) {
                    selectedPromptId = draggedIndex.toString();
                }
                
                draggedIndex = overIndex;
                savePrompts();
                renderPromptList();
            }
        });

        card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
            draggedIndex = null;
            renderPromptList();
        });
    };

    // ===== DUPLICAR PROMPT =====
    const duplicatePrompt = (idx) => {
        const source = customPrompts[idx];
        if (!source) return;

        const copy = {
            name: `${source.name} (Cópia)`,
            text: source.text,
            includeJson: source.includeJson
        };

        customPrompts.splice(idx + 1, 0, copy);
        selectedPromptId = (idx + 1).toString();
        savePrompts();
        renderPromptList();
    };

    // ===== EXCLUIR PROMPT =====
    const deletePrompt = (idx) => {
        const p = customPrompts[idx];
        if (!p) return;

        if (!confirm(`Excluir a diretriz "${p.name}"?`)) return;

        customPrompts.splice(idx, 1);
        if (selectedPromptId === idx.toString()) {
            selectedPromptId = 'default';
        } else if (parseInt(selectedPromptId) > idx) {
            selectedPromptId = (parseInt(selectedPromptId) - 1).toString();
        }
        savePrompts();
        renderPromptList();
    };

    // ===== RESET DEFAULT PROMPT =====
    const resetDefaultPrompt = () => {
        if (!confirm("Restaurar o prompt Padrão original do sistema?")) return;
        defaultPromptOverride = {
            text: DEFAULT_PROMPT_TEXT,
            includeJson: true
        };
        savePrompts();
        renderPromptList();
        alert("Diretriz padrão restaurada com sucesso.");
    };

    // ===== EDITOR LOGIC =====
    const openEditor = (idx) => {
        editingIndex = idx;
        promptEditorCard.classList.remove('hidden');

        if (idx === 'default') {
            editorTitle.textContent = '✏️ Editar Diretriz Padrão';
            editorPromptName.value = '📌 Padrão';
            editorPromptName.disabled = true;
            editorPromptText.value = defaultPromptOverride.text;
            editorIncludeJson.checked = defaultPromptOverride.includeJson;
        } else if (idx === null) {
            editorTitle.textContent = '➕ Criar Diretriz';
            editorPromptName.value = '';
            editorPromptName.disabled = false;
            editorPromptText.value = DEFAULT_PROMPT_TEXT;
            editorIncludeJson.checked = true;
        } else {
            const p = customPrompts[idx];
            editorTitle.textContent = '✏️ Editar Diretriz';
            editorPromptName.value = p.name;
            editorPromptName.disabled = false;
            editorPromptText.value = p.text;
            editorIncludeJson.checked = p.includeJson;
        }

        // Scroll to editor card
        setTimeout(() => promptEditorCard.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100);
    };

    const closeEditor = () => {
        promptEditorCard.classList.add('hidden');
        editingIndex = null;
    };

    cancelEditorBtn.addEventListener('click', closeEditor);

    saveEditorBtn.addEventListener('click', () => {
        const name = editorPromptName.value.trim();
        const text = editorPromptText.value.trim();
        const includeJson = editorIncludeJson.checked;

        if (!name) { alert('Digite o nome da diretriz.'); editorPromptName.focus(); return; }
        if (!text) { alert('O texto da instrução está vazio.'); editorPromptText.focus(); return; }

        if (editingIndex === 'default') {
            defaultPromptOverride = { text, includeJson };
        } else if (editingIndex === null) {
            customPrompts.push({ name, text, includeJson });
            selectedPromptId = (customPrompts.length - 1).toString();
        } else {
            customPrompts[editingIndex] = { name, text, includeJson };
        }

        savePrompts();
        renderPromptList();
        closeEditor();
    });

    createNewPromptBtn.addEventListener('click', () => {
        openEditor(null);
    });

    // ===== LIVE PREVIEW EXPAND/COLLAPSE =====
    togglePreviewTextBtn.addEventListener('click', () => {
        const isCollapsed = livePreviewContainer.classList.contains('collapsed');
        if (isCollapsed) {
            livePreviewContainer.classList.remove('collapsed');
            togglePreviewTextBtn.textContent = 'Ocultar';
        } else {
            livePreviewContainer.classList.add('collapsed');
            togglePreviewTextBtn.textContent = 'Ver texto';
        }
    });

    // ===== EXPORT PROMPTS =====
    exportPromptsBtn.addEventListener('click', () => {
        const dataStr = JSON.stringify({
            version: "socialtxt-v2",
            defaultPromptOverride,
            customPrompts
        }, null, 2);

        const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
        const exportFileDefaultName = 'socialtxt-diretrizes.json';

        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();
    });

    // ===== IMPORT PROMPTS =====
    importPromptsBtn.addEventListener('click', () => {
        importFileInput.click();
    });

    importFileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (event) => {
            try {
                const parsed = JSON.parse(event.target.result);
                if (parsed.version === "socialtxt-v2") {
                    if (parsed.defaultPromptOverride) defaultPromptOverride = parsed.defaultPromptOverride;
                    if (parsed.customPrompts) customPrompts = parsed.customPrompts;
                    selectedPromptId = 'default';
                    savePrompts();
                    renderPromptList();
                    alert("Diretrizes importadas com sucesso!");
                } else {
                    alert("Formato de arquivo incompatível.");
                }
            } catch (err) {
                alert("Erro ao ler o arquivo JSON: " + err.message);
            }
        };
        reader.readAsText(file);
    });

    // ===== SIDEBAR LIFE CYCLE =====
    openSidebarBtn.addEventListener('click', () => {
        sidebar.classList.remove('collapsed');
        sidebarOverlay.classList.add('active');
        document.getElementById('mainContent').classList.remove('expanded');
    });

    closeSidebarBtn.addEventListener('click', () => {
        sidebar.classList.add('collapsed');
        sidebarOverlay.classList.remove('active');
        document.getElementById('mainContent').classList.add('expanded');
    });

    sidebarOverlay.addEventListener('click', () => {
        sidebar.classList.add('collapsed');
        sidebarOverlay.classList.remove('active');
        document.getElementById('mainContent').classList.add('expanded');
    });

    // ===== CREDENCIAIS IA =====
    saveSettingsBtn.addEventListener('click', async () => {
        const apiKey = apiKeyInput.value.trim();
        const apiUrl = apiProviderSelect.value.trim();
        const model = modelInput.value.trim();

        // Salvar localmente no localStorage para redundância/cache
        localStorage.setItem('socialTxt_apiProvider', apiUrl);
        localStorage.setItem('socialTxt_apiKey', apiKey);
        localStorage.setItem('socialTxt_model', model);

        // Salvar persistentemente no backend
        try {
            const resp = await fetch(window.location.origin + '/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_key: apiKey,
                    api_url: apiUrl,
                    model: model
                })
            });
            if (!resp.ok) throw new Error("Erro ao salvar no backend");

            const originalText = saveSettingsBtn.textContent;
            saveSettingsBtn.textContent = '✅ Salvo!';
            setTimeout(() => saveSettingsBtn.textContent = originalText, 2000);
        } catch (e) {
            console.error("Erro ao salvar credenciais no backend:", e);
            alert('Aviso: As configurações foram salvas localmente no navegador, mas falhou ao salvar de forma persistente no servidor: ' + e.message);
        }
    });

    // ===== UPLOAD DE COOKIES =====
    uploadCookiesBtn.addEventListener('click', async () => {
        const file = cookieFileInput.files[0];
        if (!file) {
            cookieUploadStatus.textContent = '❌ Selecione um arquivo (.txt ou .json) primeiro.';
            cookieUploadStatus.style.color = 'var(--danger)';
            return;
        }

        uploadCookiesBtn.textContent = 'Enviando...';
        uploadCookiesBtn.disabled = true;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const resp = await fetch(window.location.origin + '/api/upload_cookies', {
                method: 'POST',
                body: formData
            });
            const data = await resp.json();
            
            if (resp.ok) {
                cookieUploadStatus.textContent = '✅ ' + data.message;
                cookieUploadStatus.style.color = 'var(--success)';
                cookieFileInput.value = ''; // limpa o input
            } else {
                cookieUploadStatus.textContent = '❌ ' + (data.detail || 'Erro ao enviar');
                cookieUploadStatus.style.color = 'var(--danger)';
            }
        } catch (e) {
            cookieUploadStatus.textContent = '❌ Erro de conexão com o servidor';
            cookieUploadStatus.style.color = 'var(--danger)';
        } finally {
            uploadCookiesBtn.textContent = '📤 Enviar Cookies';
            uploadCookiesBtn.disabled = false;
        }
    });

    // ===== BUSCAR MODELOS =====
    fetchModelsBtn.addEventListener('click', async () => {
        const apiKey = apiKeyInput.value.trim();
        const apiUrl = apiProviderSelect.value.trim();

        if (!apiKey) { alert('Insira a chave da API primeiro.'); return; }

        fetchModelsBtn.textContent = '⏳';
        fetchModelsBtn.disabled = true;

        try {
            let baseUrl = apiUrl.replace('/chat/completions', '');
            if (!baseUrl.endsWith('/v1')) baseUrl += '/v1';

            const resp = await fetch(`${baseUrl}/models`, {
                headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' }
            });

            if (!resp.ok) throw new Error(`Erro (${resp.status})`);

            const data = await resp.json();
            modelDatalist.innerHTML = '';

            if (data.data && Array.isArray(data.data)) {
                data.data.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m.id;
                    modelDatalist.appendChild(opt);
                });
                alert(`${data.data.length} modelos carregados!`);
            } else {
                throw new Error("Formato de resposta desconhecido.");
            }
        } catch (err) {
            alert('Erro ao buscar modelos: ' + err.message);
        } finally {
            fetchModelsBtn.textContent = '🔄';
            fetchModelsBtn.disabled = false;
        }
    });

    // ===== AUX: RETORNAR PROMPT E ATRIBUTO JSON ATIVO =====
    const getActivePromptData = () => {
        if (selectedPromptId === 'default') {
            return {
                text: defaultPromptOverride.text,
                includeJson: defaultPromptOverride.includeJson
            };
        }
        const idx = parseInt(selectedPromptId);
        if (customPrompts[idx]) {
            return {
                text: customPrompts[idx].text,
                includeJson: customPrompts[idx].includeJson
            };
        }
        return {
            text: defaultPromptOverride.text,
            includeJson: defaultPromptOverride.includeJson
        };
    };

    // ===== SUBMIT FORMULARIO =====
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = urlInput.value.trim();
        if (!url) return;

        const apiKey = localStorage.getItem('socialTxt_apiKey');
        const apiProvider = localStorage.getItem('socialTxt_apiProvider');
        const model = localStorage.getItem('socialTxt_model');
        const promptData = getActivePromptData();

        submitBtn.disabled = true;
        btnText.classList.add('hidden');
        loader.classList.remove('hidden');
        resultSection.classList.add('hidden');

        try {
            const resp = await fetch(window.location.origin + '/api/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url,
                    detail: detailSelect.value,
                    language: langSelect.value,
                    api_key: apiKey || undefined,
                    api_url: apiProvider || undefined,
                    model: model || undefined,
                    prompt_override: promptData.text,
                    include_json_requirement: promptData.includeJson
                })
            });

            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Erro no processamento');
            }

            renderResult(await resp.json(), promptData.includeJson);
        } catch (err) {
            alert('Erro: ' + err.message + '\n\nVerifique se sua chave API está correta no painel lateral ⚙️.');
        } finally {
            submitBtn.disabled = false;
            btnText.classList.remove('hidden');
            loader.classList.add('hidden');
        }
    });

    // ===== RESET SCREEN =====
    resetBtn.addEventListener('click', () => {
        resultSection.classList.add('hidden');
        urlInput.value = '';
        urlInput.focus();
    });

    // ===== RENDER RESULT =====
    function renderResult(data, isJsonMode) {
        resultTitle.textContent = data.possible_title || 'Resumo do Conteúdo';
        typeBadge.textContent = data.content_type || 'Link';

        if (isJsonMode) {
            structuredResultBlock.classList.remove('hidden');
            plainTextResultBlock.classList.add('hidden');

            summaryText.textContent = data.summary || 'Nenhum resumo gerado.';

            keyPointsList.innerHTML = '';
            if (data.key_points && data.key_points.length > 0) {
                data.key_points.forEach(point => {
                    const li = document.createElement('li');
                    li.textContent = point;
                    keyPointsList.appendChild(li);
                });
            } else {
                const li = document.createElement('li');
                li.textContent = 'Nenhum ponto principal extraído.';
                li.style.color = 'var(--text-muted)';
                keyPointsList.appendChild(li);
            }
        } else {
            structuredResultBlock.classList.add('hidden');
            plainTextResultBlock.classList.remove('hidden');
            plainTextContent.textContent = data.summary || 'Nenhuma resposta retornada.';
        }

        // Warnings
        warningsContainer.innerHTML = '';
        if (data.warnings && data.warnings.length > 0) {
            data.warnings.forEach(w => {
                const p = document.createElement('p');
                p.textContent = `⚠️ ${w}`;
                warningsContainer.appendChild(p);
            });
            warningsContainer.classList.remove('hidden');
        } else {
            warningsContainer.classList.add('hidden');
        }

        // Fade-in animation
        resultSection.style.opacity = '0';
        resultSection.style.transform = 'translateY(15px)';
        resultSection.classList.remove('hidden');
        void resultSection.offsetWidth;
        resultSection.style.opacity = '1';
        resultSection.style.transform = 'translateY(0)';

        setTimeout(() => resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    }

    // ===== INITIAL SIDEBAR STATE BY SCREEN SIZE =====
    const initSidebar = () => {
        if (window.innerWidth > 900) {
            sidebar.classList.remove('collapsed');
            document.getElementById('mainContent').classList.remove('expanded');
        } else {
            sidebar.classList.add('collapsed');
            document.getElementById('mainContent').classList.add('expanded');
        }
    };

    // ===== API TABS SWITCHER =====
    const setupApiTabs = () => {
        const tabRestBtn = document.getElementById('tab-rest-btn');
        const tabMcpBtn = document.getElementById('tab-mcp-btn');
        const contentRest = document.getElementById('content-rest');
        const contentMcp = document.getElementById('content-mcp');

        if (!tabRestBtn || !tabMcpBtn || !contentRest || !contentMcp) return;

        tabRestBtn.addEventListener('click', () => {
            tabRestBtn.classList.add('active');
            tabMcpBtn.classList.remove('active');
            contentRest.classList.remove('hidden');
            contentMcp.classList.add('hidden');
        });

        tabMcpBtn.addEventListener('click', () => {
            tabMcpBtn.classList.add('active');
            tabRestBtn.classList.remove('active');
            contentMcp.classList.remove('hidden');
            contentRest.classList.add('hidden');
        });
    };

    // ===== INICIALIZAÇÃO =====
    initSidebar();
    loadSettings();
    setupApiTabs();
});
