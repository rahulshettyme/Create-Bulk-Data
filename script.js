// =============================================
// DATA GENERATE SCRIPT (Production Environment)
// =============================================
/**
 * CRITICAL ARCHITECTURE RULE:
 * This file handles the "Bulk Execution" of scripts (Production).
 * The Development/Test logic is located in `Data Generate/script_management_v2.js`.
 * 
 * Logic regarding Attributes, API URLs, and Data Injection MUST match `script_management_v2.js`.
 */

// State
let authToken = null;
let currentEnvironment = null;
let currentTenant = null;
let selectedDataType = null;
let uploadedData = [];
let executionResults = [];
let savedLocations = [];
let ENVIRONMENT_API_URLS = {};
let ENVIRONMENT_URLS = {};
let loginComponent = null;

// Load Env URLs on start
async function loadEnvUrls() {
    try {
        const res = await fetch('/api/env-urls');
        const data = await res.json();
        ENVIRONMENT_API_URLS = data.environment_api_urls || {};
        ENVIRONMENT_URLS = data.environment_urls || {};
        console.log('Loaded Environment URLs:', Object.keys(ENVIRONMENT_API_URLS));
    } catch (e) {
        console.error('Failed to load env URLs:', e);
    }
}


// Helper to get URLs for environment
function getEnvUrls(environment) {
    let apiBaseUrl = null;
    let frontendUrl = null;

    if (environment) {
        // Case-insensitive lookup
        const apiKeys = Object.keys(ENVIRONMENT_API_URLS);
        const envKey = apiKeys.find(k => k.toLowerCase() === environment.toLowerCase());
        if (envKey) {
            apiBaseUrl = ENVIRONMENT_API_URLS[envKey];
        }

        const feKeys = Object.keys(ENVIRONMENT_URLS);
        const feKey = feKeys.find(k => k.toLowerCase() === environment.toLowerCase());
        if (feKey) {
            frontendUrl = ENVIRONMENT_URLS[feKey];
        }
    }
    return { apiBaseUrl, frontendUrl };
}

// Constants for coordinate generation
const ACRE_M2 = 4046.8564224;

// =============================================
// RESET STATE (Partial Reset - Persists Login)
// =============================================
function resetState() {
    // DO NOT CLEAR AUTH TOKEN HERE
    // authToken = null;
    // currentEnvironment = null;
    // currentTenant = null;

    uploadedData = [];
    executionResults = [];

    // Reset UI
    if (elements.fileName) elements.fileName.textContent = 'Supported formats: .xlsx, .xls';
    if (elements.fileUpload) elements.fileUpload.value = '';
    if (elements.executeBtn) {
        elements.executeBtn.disabled = true;
        elements.executeBtn.textContent = '🚀 Execute Data Creation';
    }
    if (elements.resultsSection) elements.resultsSection.classList.add('hidden');
    if (elements.progressBar) elements.progressBar.style.width = '0%';
    if (elements.progressText) elements.progressText.textContent = '0 / 0';
    if (elements.passCount) elements.passCount.textContent = '0';
    if (elements.failCount) elements.failCount.textContent = '0';
    if (elements.resultsTbody) elements.resultsTbody.innerHTML = '';
}

// Full Logout
function fullLogout() {
    authToken = null;
    currentEnvironment = null;
    currentTenant = null;

    // Reset Data
    resetState();

    // UI Updates
    if (elements.sessionContainer) elements.sessionContainer.classList.add('hidden');
    if (elements.loginComponentContainer) elements.loginComponentContainer.classList.remove('hidden');

    // Disable Upload Area
    if (elements.uploadWorkflowContainer) {
        elements.uploadWorkflowContainer.classList.add('disabled-area');
        elements.uploadWorkflowContainer.style.opacity = '0.5';
        elements.uploadWorkflowContainer.style.pointerEvents = 'none';
    }
}

// Template Definitions
const TEMPLATES = {


};



// DOM Elements
const elements = {
    dataNeededForSelect: document.getElementById('data-needed-for'),
    dataTypeSelect: document.getElementById('data-type-select'), // Hidden input
    scriptDisplay: document.getElementById('script-display'),
    scriptDropdown: document.getElementById('script-dropdown-container'),
    scriptMenu: document.getElementById('script-dropdown-menu'),
    scriptSearch: document.getElementById('script-search'),
    scriptSearchClear: document.getElementById('script-search-clear'),
    scriptList: document.getElementById('script-list'),

    templateInfo: document.getElementById('template-info'),
    templateTypeName: document.getElementById('template-type-name'),
    templateColumns: document.getElementById('template-columns'),
    exportBtn: document.getElementById('export-btn'),
    importBtn: document.getElementById('import-btn'),
    loginSection: document.getElementById('login-section'),
    loginFormContainer: document.getElementById('login-form-container'),

    // Login elements replaced by component but we keep session container
    sessionContainer: document.getElementById('session-container'),
    sessionInfo: document.getElementById('session-info'),

    fileUploadArea: document.getElementById('file-upload-area'),
    fileUpload: document.getElementById('file-upload'),
    fileName: document.getElementById('file-name'),
    executeBtn: document.getElementById('execute-btn'),
    resultsSection: document.getElementById('results-section'),
    progressText: document.getElementById('progress-text'),
    progressBar: document.getElementById('progress-bar'),
    passCount: document.getElementById('pass-count'),
    failCount: document.getElementById('fail-count'),
    executionTime: document.getElementById('execution-time'),
    downloadResultsBtn: document.getElementById('download-results-btn'),
    resultsTbody: document.getElementById('results-tbody'),
    // Boundary elements
    boundaryConfig: document.getElementById('boundary-config'),
    savedLocationSelect: document.getElementById('saved-location-select'),
    deleteLocationBtn: document.getElementById('delete-location-btn'),
    minLat: document.getElementById('min-lat'),
    maxLat: document.getElementById('max-lat'),
    minLong: document.getElementById('min-long'),
    maxLong: document.getElementById('max-long'),
    locationName: document.getElementById('location-name'),
    saveLocationBtn: document.getElementById('save-location-btn'),

    // Import Script Elements
    toggleImportLink: document.getElementById('toggle-import-section'),
    importScriptSection: document.getElementById('import-script-section'),
    importScriptFile: document.getElementById('import-script-file'),
    importScriptJson: document.getElementById('import-script-json'),
    cancelImportBtn: document.getElementById('cancel-import-btn'),
    confirmImportBtn: document.getElementById('confirm-import-btn'),

    // Workflow Container
    uploadWorkflowContainer: document.getElementById('upload-workflow-container'),
    loginComponentContainer: document.getElementById('login-component-container'),

    // Additional Attributes
    additionalAttributesSection: document.getElementById('additional-attributes-section'),
    enableAdditionalAttributes: document.getElementById('enable-additional-attributes'),
    additionalAttributesInputContainer: document.getElementById('additional-attributes-input-container'),
    additionalAttributesInput: document.getElementById('additional-attributes-input'),
    gdprSection: document.getElementById('gdpr-section'),
    isGdprTenant: document.getElementById('is-gdpr-tenant'),

    // Advanced Settings
    advancedSettingsSection: document.getElementById('advanced-settings-section'),
    groupBySelect: document.getElementById('group-by-select'),

    // Script Description
    scriptDescriptionContainer: document.getElementById('script-description-container'),
    scriptDescriptionText: document.getElementById('script-description-text'),

    // Area Audit V2 Elements
    v2SpecificConfig: document.getElementById('v2-specific-config'),
    v2AreaSize: document.getElementById('v2-area-size'),
    v2AreaUnit: document.getElementById('v2-area-unit'),
    v2LocationName: document.getElementById('v2-location-name'),
    v2ResolveBtn: document.getElementById('v2-resolve-btn')
};

// =============================================
// TEAM & DATA TYPE SELECTION
// =============================================

const TEAM_SCRIPTS = {
    cs_team: [],
    qa_team: []
};


// =============================================
// DYNAMIC SCRIPT LOADING
// =============================================
async function loadCustomScripts() {
    try {
        const res = await fetch('/api/scripts/custom', { cache: 'no-store' });
        const scripts = await res.json();

        console.log(`[LoadScripts] Fetched ${scripts.length} scripts`);

        scripts.forEach(script => {
            // Register Template
            // Use the filename (or a key) as the ID, ensuring it doesn't conflict
            const scriptKey = script.name.replace('.py', '');

            console.log(`[LoadScripts] Processing: ${scriptKey}, Team: ${script.team}`);

            TEMPLATES[scriptKey] = {
                name: script.display_name || script.name.replace('.py', ''),
                columns: (script.columns || []).map(c => ({
                    header: c.name,
                    key: c.name.toLowerCase().replace(/ /g, '_'),
                    required: c.type === 'Mandatory',
                    description: c.description
                })),
                description: script.description || "", // Store Description
                isCustom: true,
                filename: script.filename || script.name,
                requiresLogin: script.requiresLogin,
                allowAdditionalAttributes: script.allowAdditionalAttributes,
                additionalAttributes: script.additionalAttributes || [],
                isMultithreaded: script.isMultithreaded,
                groupByColumn: script.groupByColumn,
                batchSize: script.batchSize,
                enableGeofencing: script.enableGeofencing,
                outputConfig: script.outputConfig // Pass outputConfig 
            };

            // Add to Team Lists
            // script.team should be 'QA' or 'CS' or 'Both'
            const team = (script.team || 'QA').toLowerCase();
            if (team.includes('qa') || team === 'both') {
                if (!TEAM_SCRIPTS.qa_team.includes(scriptKey)) {
                    TEAM_SCRIPTS.qa_team.push(scriptKey);
                }
            }
            if (team.includes('cs') || team === 'both') {
                if (!TEAM_SCRIPTS.cs_team.includes(scriptKey)) {
                    TEAM_SCRIPTS.cs_team.push(scriptKey);
                }
            }
        });

        console.log('Custom scripts loaded:', scripts.length);
        console.log('Teams:', JSON.stringify(TEAM_SCRIPTS, null, 2));

        // Re-render if team is selected
        if (elements.dataNeededForSelect && elements.dataNeededForSelect.value) {
            handleTeamSelection(elements.dataNeededForSelect.value);
        }

    } catch (e) {
        console.error('Failed to load custom scripts:', e);
    }
}

// Call on load
loadCustomScripts();

// =============================================
// REUSABLE SEARCHABLE DROPDOWN LOGIC
// =============================================
function setupSearchableDropdown(config) {
    const { display, menu, search, searchClear, list, hiddenInput, onSelect } = config;

    // Toggle Menu
    display.addEventListener('click', (e) => {
        if (display.classList.contains('disabled')) return;
        e.stopPropagation();
        // Close others if needed (optional)
        document.querySelectorAll('.custom-menu.show').forEach(m => {
            if (m !== menu) m.classList.remove('show');
        });
        menu.classList.toggle('show');
        if (menu.classList.contains('show')) {
            search.focus();
        }
    });

    // Search Filter
    search.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();

        // Toggle Clear Icon
        if (term.length > 0) {
            searchClear.classList.add('visible');
        } else {
            searchClear.classList.remove('visible');
        }

        const items = list.querySelectorAll('.custom-item');
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            if (text.includes(term)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    });

    // Clear Search
    if (searchClear) {
        searchClear.addEventListener('click', (e) => {
            e.stopPropagation();
            search.value = '';
            searchClear.classList.remove('visible');
            const items = list.querySelectorAll('.custom-item');
            items.forEach(item => item.style.display = 'block');
            search.focus();
        });
    }

    // Select Item (Event Delegation)
    list.addEventListener('click', (e) => {
        if (e.target.classList.contains('custom-item')) {
            const value = e.target.getAttribute('data-value');
            const text = e.target.textContent;

            // Update UI
            display.textContent = text;
            display.style.color = '#264554'; // Ensure text color is reset/correct
            hiddenInput.value = value;

            // Highlight selected
            list.querySelectorAll('.custom-item').forEach(item => item.classList.remove('selected'));
            e.target.classList.add('selected');

            // Hide menu
            menu.classList.remove('show');
            search.value = ''; // Reset search
            if (searchClear) searchClear.classList.remove('visible'); // Reset clear icon
            const items = list.querySelectorAll('.custom-item'); // Reset list visibility
            items.forEach(item => item.style.display = 'block');

            // Trigger callback
            if (typeof onSelect === 'function') {
                onSelect(value, text);
            }
        }
    });

    // Close on click outside
    document.addEventListener('click', (e) => {
        if (!display.contains(e.target) && !menu.contains(e.target)) {
            menu.classList.remove('show');
        }
    });
}

// Initialize Dropdowns
// Script Dropdown
setupSearchableDropdown({
    display: elements.scriptDisplay,
    menu: elements.scriptMenu,
    search: elements.scriptSearch,
    searchClear: elements.scriptSearchClear,
    list: elements.scriptList,
    hiddenInput: elements.dataTypeSelect,
    onSelect: (value) => {
        // Trigger existing logic
        handleScriptSelection(value);
    }
});

// Environment Dropdown Logic REMOVED (Handled by Component)

// Extracted function for populating scripts and handling UI based on team selection
function handleTeamSelection(team) {
    console.log(`[handleTeamSelection] Called with team: ${team}`);
    try {
        resetState();
        let availableScripts = TEAM_SCRIPTS[team] || [];
        console.log(`[handleTeamSelection] Found ${availableScripts.length} scripts for ${team}`);

        // Sort scripts by name
        availableScripts.sort((a, b) => {
            const nameA = TEMPLATES[a] ? TEMPLATES[a].name.toLowerCase() : '';
            const nameB = TEMPLATES[b] ? TEMPLATES[b].name.toLowerCase() : '';
            return nameA.localeCompare(nameB);
        });

        // Handle Environment Visibility based on Team
        if (team === 'cs_team') {
            if (loginComponent) {
                loginComponent.setEnvironment('Prod', true);
            }
        } else {
            if (loginComponent) {
                loginComponent.setEnvironment('QA1', false);
            }
        }

        // Clear list
        elements.scriptList.innerHTML = '';

        // Populate list
        availableScripts.forEach(scriptKey => {
            const template = TEMPLATES[scriptKey];
            if (template) {
                const li = document.createElement('li');
                li.classList.add('custom-item'); // UPDATED CLASS
                li.setAttribute('data-value', scriptKey);
                li.textContent = template.name;
                elements.scriptList.appendChild(li);
            }
        });

        // Enable Dropdown
        console.log('[handleTeamSelection] Enabling dropdown');
        elements.scriptDisplay.classList.remove('disabled');
        elements.scriptDisplay.textContent = 'Select Script';
        elements.dataTypeSelect.value = "";

        // Reset UI state
        elements.templateInfo.classList.add('hidden');
        elements.boundaryConfig.classList.add('hidden');
        elements.exportBtn.disabled = true;
        elements.importBtn.disabled = true;
        selectedDataType = null;
    } catch (err) {
        console.error('[handleTeamSelection] Error:', err);
        alert('Error selecting team: ' + err.message);
    }
}

// Asset Reference Data Cache
let assetRefData = {
    farmers: [],
    soilTypes: [],
    irrigationTypes: []
};

// Tag Reference Data Cache
let tagRefData = [];

async function loadAssetReferenceData() {
    try {
        console.log('Loading asset reference data...');
        const query = `?environment=${currentEnvironment}&tenant=${currentTenant}`;
        const [farmers, soils, irrigations] = await Promise.all([
            fetch(`/api/data-generate/farmers-list${query}`, { headers: { 'Authorization': `Bearer ${authToken}` } }).then(r => r.json()),
            fetch(`/api/data-generate/soil-types${query}`, { headers: { 'Authorization': `Bearer ${authToken}` } }).then(r => r.json()),
            fetch(`/api/data-generate/irrigation-types${query}`, { headers: { 'Authorization': `Bearer ${authToken}` } }).then(r => r.json())
        ]);

        assetRefData.farmers = Array.isArray(farmers) ? farmers : [];
        assetRefData.soilTypes = Array.isArray(soils) ? soils : [];
        assetRefData.irrigationTypes = Array.isArray(irrigations) ? irrigations : [];
        console.log('Asset reference data loaded');
    } catch (e) {
        console.error('Failed to load reference data', e);
        throw new Error('Failed to load reference data: ' + e.message);
    }
}


if (elements.dataNeededForSelect) {
    elements.dataNeededForSelect.addEventListener('change', (e) => {
        handleTeamSelection(e.target.value);
    });
}

// Initialize
function init() {
    // Load Env URLs
    loadEnvUrls();

    // Load Scripts
    loadCustomScripts();
    loadSavedLocations();

    // If team is already selected, populate scripts
    if (elements.dataNeededForSelect && elements.dataNeededForSelect.value) {
        handleTeamSelection(elements.dataNeededForSelect.value);
    }
}
init();

// Additional Attributes Toggle Listener
if (elements.enableAdditionalAttributes) {
    elements.enableAdditionalAttributes.addEventListener('change', (e) => {
        if (e.target.checked) {
            elements.additionalAttributesInputContainer.classList.remove('hidden');
        } else {
            elements.additionalAttributesInputContainer.classList.add('hidden');
        }
    });
}

async function handleScriptSelection(value) {
    resetState();
    selectedDataType = value;

    // REFACTOR: Sync with Live Metadata first
    try {
        // Resolve Filename from Template if possible
        let filenameForSync = value;
        const potentialTemplate = TEMPLATES[value];
        if (potentialTemplate && potentialTemplate.filename) {
            filenameForSync = potentialTemplate.filename;
        }
        await syncTemplateWithLiveMeta(filenameForSync);
    } catch (e) { console.warn("Live Sync failed, falling back to registry.", e); }

    const template = TEMPLATES[selectedDataType];

    // Show Description
    if (template && template.description) {
        if (elements.scriptDescriptionContainer) {
            elements.scriptDescriptionContainer.classList.remove('hidden');
            elements.scriptDescriptionText.textContent = template.description;
        }
    } else {
        if (elements.scriptDescriptionContainer) {
            elements.scriptDescriptionContainer.classList.add('hidden');
            elements.scriptDescriptionText.textContent = '';
        }
    }

    // Show/hide boundary config based on type
    // Updated to match filename-derived keys (underscores) and remove team restriction
    const needsBoundary = (
        selectedDataType === 'Generate_Coordinates' ||
        selectedDataType === 'Area_Audit' ||
        selectedDataType === 'Generate Coordinates' ||
        selectedDataType === 'Area Audit' ||
        selectedDataType === 'Area Audit V2' ||
        selectedDataType === 'Area_Audit_V2.py'
    );

    if (needsBoundary) {
        elements.boundaryConfig.classList.remove('hidden');
    } else {
        elements.boundaryConfig.classList.add('hidden');
    }

    // Reset Additional Attributes UI
    if (elements.additionalAttributesSection) elements.additionalAttributesSection.classList.add('hidden');
    if (elements.enableAdditionalAttributes) elements.enableAdditionalAttributes.checked = false;
    if (elements.additionalAttributesInputContainer) elements.additionalAttributesInputContainer.classList.add('hidden');
    if (elements.additionalAttributesInput) elements.additionalAttributesInput.value = '';

    // Reset GDPR UI
    if (elements.gdprSection) elements.gdprSection.classList.add('hidden');
    if (elements.isGdprTenant) elements.isGdprTenant.checked = false;

    // Show/Hide Attributes based on Template Metadata
    if (template && template.allowAdditionalAttributes) {
        if (elements.additionalAttributesSection) elements.additionalAttributesSection.classList.remove('hidden');
    }

    // Show/Hide GDPR for Create Farmer
    // We check via filename relative to the converted name
    if (value === 'Create_Farmer.py' || (template && template.name && template.name.includes('Create_Farmer'))) {
        if (elements.gdprSection) elements.gdprSection.classList.remove('hidden');
    }

    // Show template info for types other than coordinates
    if (template && selectedDataType !== 'coordinates') {
        elements.templateTypeName.textContent = template.name;
        elements.templateColumns.innerHTML = template.columns
            .map(col => `<li><strong>${col.header}</strong>${col.required ? ' (required)' : ''} - ${col.description}</li>`)
            .join('');
        elements.templateInfo.classList.remove('hidden');
    } else {
        elements.templateInfo.classList.add('hidden');
    }

    // Show/Hide Dynamic Geofencing Section based on Template Metadata
    const targetLocationSection = document.getElementById('target-location-section');
    if (targetLocationSection) {
        if (template && template.enableGeofencing) {
            targetLocationSection.classList.remove('hidden');
            targetLocationSection.style.display = 'block'; // Ensure it's visible
        } else {
            targetLocationSection.classList.add('hidden');
            targetLocationSection.style.display = 'none';
        }
    }

    // --- AREA AUDIT V2 VISIBILITY ---
    if (elements.v2SpecificConfig) {
        // Check filename or friendly name
        const isV2 = value === 'Area_Audit_V2.py' || (template && template.name === 'Area Audit V2');

        if (isV2) {
            elements.v2SpecificConfig.classList.remove('hidden');
            // Ensure parent boundary config is visible
            elements.boundaryConfig.classList.remove('hidden');

            // Hide standard geofence wrapper if it exists (but likely overlaps with boundaryConfig)
            // If targetLocationSection is distinct, hide it. 
            // In our case, boundaryConfig IS the container for inputs.
        } else {
            elements.v2SpecificConfig.classList.add('hidden');
        }
    }

    // Enable buttons if template exists
    if (template) {
        elements.exportBtn.disabled = false;
        elements.importBtn.disabled = false;

        // Populate "Group By" Dropdown with columns
        if (elements.groupBySelect && elements.advancedSettingsSection) {
            elements.advancedSettingsSection.classList.remove('hidden');
            elements.groupBySelect.innerHTML = '<option value="">None (Sequential Batching)</option>';

            if (template.columns && template.columns.length > 0) {
                template.columns.forEach(col => {
                    const option = document.createElement('option');
                    option.value = col.header; // Use exact header name
                    option.textContent = col.header;
                    elements.groupBySelect.appendChild(option);
                });
            }

            // Auto-select if configured
            if (template.groupByColumn) {
                elements.groupBySelect.value = template.groupByColumn;
                if (!elements.groupBySelect.value) {
                    const match = Array.from(elements.groupBySelect.options).find(opt => opt.value.toLowerCase() === template.groupByColumn.toLowerCase());
                    if (match) elements.groupBySelect.value = match.value;
                }
            }
        }
    } else {
        elements.exportBtn.disabled = true;
        elements.importBtn.disabled = true;
        if (elements.advancedSettingsSection) elements.advancedSettingsSection.classList.add('hidden');
    }
}

// =============================================
// SAVED LOCATIONS MANAGEMENT
// =============================================
async function loadSavedLocations() {
    try {
        const res = await fetch('/api/saved-locations');
        savedLocations = await res.json();
    } catch (e) {
        console.error('Failed to load saved locations', e);
        savedLocations = [];
    }
    renderSavedLocations();
}

async function saveSavedLocations() {
    try {
        await fetch('/api/saved-locations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(savedLocations)
        });
    } catch (e) {
        console.error('Failed to save locations', e);
    }
}

function renderSavedLocations() {
    if (!elements.savedLocationSelect) return;

    savedLocations.forEach((loc, index) => {
        const option = document.createElement('option');
        option.value = index;
        option.textContent = loc.name;
        elements.savedLocationSelect.appendChild(option);
    });
}

function renderExecutionResults() {
    const table = document.querySelector('.results-table');
    const thead = table.querySelector('thead');
    const tbody = elements.resultsTbody;

    // Clear Body
    tbody.innerHTML = '';

    if (executionResults.length === 0) {
        thead.innerHTML = `<tr><th>Row</th><th>Name</th><th>Code</th><th>Status</th><th>Response</th></tr>`;
        return;
    }

    // Check if Dynamic UI is enabled for this script
    const template = TEMPLATES[selectedDataType];
    const isDynamic = template && template.outputConfig && template.outputConfig.isDynamicUI;

    if (isDynamic) {
        // --- DYNAMIC MODE (New Scripts) ---
        const sample = executionResults[0];
        const internalKeys = ['row', 'status', 'response', 'API response', 'API_Response'];

        // Use UI Mapping if available
        let dataKeys = [];
        const uiMap = template.outputConfig.uiMapping;
        if (uiMap && Array.isArray(uiMap) && uiMap.length > 0) {
            dataKeys = uiMap.map(m => m.colName).filter(c => c);
        } else {
            // Fallback
            dataKeys = Object.keys(sample).filter(k =>
                !internalKeys.includes(k) &&
                !internalKeys.includes(k.toLowerCase()) &&
                k !== 'name' && k !== 'code'
            );
        }

        // Build Header
        let headerHTML = '<tr><th>Row</th>';
        dataKeys.forEach(k => headerHTML += `<th>${k}</th>`);
        headerHTML += '</tr>';
        thead.innerHTML = headerHTML;

        executionResults.forEach((row, index) => {
            const tr = document.createElement('tr');

            // 1. Row
            const tdIndex = document.createElement('td');
            tdIndex.textContent = row.row || (index + 1);
            tr.appendChild(tdIndex);

            // 2. Data Columns (Dynamic)
            dataKeys.forEach(k => {
                const td = document.createElement('td');
                const val = row[k];
                const kLower = k.toLowerCase();

                if (kLower === 'status') {
                    // Status Styling
                    const statusVal = val || 'Unknown';
                    td.textContent = statusVal;
                    const lowerStatus = String(statusVal).toLowerCase();
                    if (lowerStatus === 'success' || lowerStatus === 'pass' || lowerStatus === 'passed') {
                        td.classList.add('status-pass');
                    } else if (lowerStatus.startsWith('fail') || lowerStatus.includes('error')) {
                        td.classList.add('status-fail');
                    } else {
                        td.classList.add('status-pending');
                    }
                } else if (kLower === 'response' || kLower === 'api response' || kLower === 'api_response') {
                    // Response Styling
                    const respVal = (val !== undefined && val !== null) ? val : '';
                    td.textContent = respVal;
                    td.title = respVal;
                } else {
                    // Default
                    td.textContent = (val !== undefined && val !== null) ? val : '-';
                }
                tr.appendChild(td);
            });

            tbody.appendChild(tr);
        });

    } else {
        // --- LEGACY MODE (Old Scripts) ---
        thead.innerHTML = `<tr><th>Row</th><th>Name</th><th>Code</th><th>Status</th><th>Response</th></tr>`;

        const seenNames = new Set();

        executionResults.forEach((row, index) => {
            const tr = document.createElement('tr');

            if (row.name) seenNames.add(String(row.name).trim().toLowerCase());

            const tdIndex = document.createElement('td');
            tdIndex.textContent = row.row || (index + 1);
            tr.appendChild(tdIndex);

            const tdName = document.createElement('td');
            tdName.textContent = row.name || '-';
            tr.appendChild(tdName);

            const tdCode = document.createElement('td');
            tdCode.textContent = row.code || '-';
            tr.appendChild(tdCode);

            const tdStatus = document.createElement('td');
            let statusVal = row.status || row.Status || 'Unknown';
            tdStatus.textContent = statusVal;
            const lowerStatus = String(statusVal).toLowerCase();
            if (lowerStatus === 'success' || lowerStatus === 'pass' || lowerStatus === 'passed') {
                tdStatus.classList.add('status-pass');
            } else if (lowerStatus.startsWith('fail') || lowerStatus.includes('error')) {
                tdStatus.classList.add('status-fail');
            } else {
                tdStatus.classList.add('status-pending');
            }
            tr.appendChild(tdStatus);

            const tdResponse = document.createElement('td');
            const respVal = row.response || row['API response'] || row.API_Response || '';
            tdResponse.textContent = respVal;
            tdResponse.title = respVal;
            tr.appendChild(tdResponse);

            tbody.appendChild(tr);
        });
    }
}

// Saved location selection
if (elements.savedLocationSelect) {
    elements.savedLocationSelect.addEventListener('change', (e) => {
        const index = e.target.value;
        if (index !== '') {
            const loc = savedLocations[parseInt(index)];
            elements.minLat.value = loc.minLat;
            elements.maxLat.value = loc.maxLat;
            elements.minLong.value = loc.minLong;
            elements.maxLong.value = loc.maxLong;
            elements.deleteLocationBtn.classList.remove('hidden');
        } else {
            elements.minLat.value = '';
            elements.maxLat.value = '';
            elements.minLong.value = '';
            elements.maxLong.value = '';
            elements.deleteLocationBtn.classList.add('hidden');
        }
    });
}

// Save location button
if (elements.saveLocationBtn) {
    elements.saveLocationBtn.addEventListener('click', () => {
        const name = elements.locationName.value.trim();
        const minLat = parseFloat(elements.minLat.value);
        const maxLat = parseFloat(elements.maxLat.value);
        const minLong = parseFloat(elements.minLong.value);
        const maxLong = parseFloat(elements.maxLong.value);

        if (!name) {
            alert('Please enter a name for this location');
            return;
        }
        if (isNaN(minLat) || isNaN(maxLat) || isNaN(minLong) || isNaN(maxLong)) {
            alert('Please fill in all boundary values');
            return;
        }

        savedLocations.push({ name, minLat, maxLat, minLong, maxLong });
        saveSavedLocations();
        // Update both text and UI
        // Actually loadSavedLocations re-renders everything
        loadSavedLocations();
        alert('Location saved!');
        elements.locationName.value = '';
    });
}

// Delete location button
if (elements.deleteLocationBtn) {
    elements.deleteLocationBtn.addEventListener('click', () => {
        const index = elements.savedLocationSelect.value;
        if (index !== '') {
            if (confirm('Delete this saved location?')) {
                savedLocations.splice(parseInt(index), 1);
                saveSavedLocations();
                loadSavedLocations();
                elements.minLat.value = '';
                elements.maxLat.value = '';
                elements.minLong.value = '';
                elements.maxLong.value = '';
                elements.deleteLocationBtn.classList.add('hidden');
                alert('Location deleted');
            }
        }
    });
}

// =============================================
// FILE UPLOAD & PROCESSING
// =============================================

if (elements.fileUpload) {
    elements.fileUpload.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            elements.fileName.textContent = file.name;
            elements.executeBtn.disabled = true; // Wait for processing
            elements.executeBtn.textContent = '⏳ Processing File...';
            processFile(file);
        }
    });
}

function processFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const data = new Uint8Array(e.target.result);
            const workbook = XLSX.read(data, { type: 'array' });
            const sheetName = workbook.SheetNames[0];
            const sheet = workbook.Sheets[sheetName];
            uploadedData = XLSX.utils.sheet_to_json(sheet);

            console.log('Processed File Data:', uploadedData);
            elements.executeBtn.disabled = false;
            elements.executeBtn.textContent = '🚀 Execute Data Creation'; // Ready
        } catch (error) {
            console.error('Error processing file:', error);
            alert('Error processing file. Please ensure it is a valid Excel file.');
        }
    };
    reader.readAsArrayBuffer(file);
}



elements.downloadResultsBtn.addEventListener('click', () => {
    if (executionResults.length === 0) return alert('No results to download');

    let ws;
    // Check if Dynamic UI is enabled
    const template = TEMPLATES[selectedDataType];
    const isDynamic = template && template.outputConfig && template.outputConfig.isDynamicUI;

    // Prepare Data for Export
    // We want to export exactly what is shown in UI + maybe internal fields?
    // For Dynamic, use all keys.
    const exportData = executionResults.map(r => {
        // Clone to avoid mutating original
        const flat = { ...r };
        delete flat.row; // Remove internal row index
        return flat;
    });

    if (isDynamic) {
        // Dynamic Headers: Gather ALL unique keys from all rows (in case sparse)
        const allKeys = new Set();
        const internalKeys = ['row', 'status', 'response', 'API response', 'API_Response', 'name', 'code'];
        // We prioritize explicit keys, but for Excel export we want everything usually.
        // But maybe sort them nicely?

        // 1. Always 'Row' first? NO, User requested removal.
        const definedHeaders = [];

        // 2. Then Data Keys
        exportData.forEach(row => Object.keys(row).forEach(k => {
            if (!definedHeaders.includes(k) && !internalKeys.includes(k)) allKeys.add(k);
        }));

        // 3. Then Standard Endings
        const endHeaders = ['name', 'code', 'status', 'response']; // If they exist locally

        const extraKeys = Array.from(allKeys);

        // 3. Final Order: Defined + Extras + Endings
        // Check which endings actually exist
        const presentEndings = endHeaders.filter(h => exportData.some(r => r[h] !== undefined));

        const finalHeaders = [...definedHeaders, ...extraKeys, ...presentEndings];

        ws = XLSX.utils.json_to_sheet(exportData, { header: finalHeaders });
    } else {
        // Legacy: Row, Name, Code, Status, Response
        // But user might have extra keys even in legacy?
        // Default behavior (random/alpha order usually) + json_to_sheet auto-detect
        // Let's just use auto-detect but ensure Row is first if possible?
        ws = XLSX.utils.json_to_sheet(exportData);
    }
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Results');

    const fileName = `Results_${selectedDataType}_${new Date().toISOString().slice(0, 10)}.xlsx`;
    XLSX.writeFile(wb, fileName);
});

// =============================================
// SHARED EXECUTION UTILITIES
// =============================================

// Execution state
let executionStartTime = null;
let executionTimerInterval = null;

// Format duration in human-readable format
function formatDuration(ms) {
    if (ms < 1000) return `${ms}ms`;
    const seconds = ms / 1000;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = (seconds % 60).toFixed(0);
    return `${minutes}m ${remainingSeconds}s`;
}

// Start execution - initializes UI and timer
function startExecution(buttonText = '⏳ Processing...') {
    executionStartTime = Date.now();

    // Reset UI
    elements.executeBtn.disabled = true;
    elements.executeBtn.textContent = buttonText;
    elements.resultsSection.classList.remove('hidden');
    elements.downloadResultsBtn.classList.add('hidden');
    elements.resultsTbody.innerHTML = '';
    elements.progressText.textContent = '0 / 0';
    elements.progressBar.style.width = '0%';
    elements.passCount.textContent = '0';
    elements.failCount.textContent = '0';
    elements.executionTime.textContent = '0.0s';
    executionResults = [];

    // Start live timer update
    if (executionTimerInterval) clearInterval(executionTimerInterval);
    executionTimerInterval = setInterval(() => {
        const elapsed = Date.now() - executionStartTime;
        elements.executionTime.textContent = formatDuration(elapsed);
    }, 100);

    return { passCount: 0, failCount: 0 };
}

// Update progress during execution
function updateProgress(current, total, passCount, failCount) {
    elements.progressText.textContent = `${current} / ${total}`;
    elements.progressBar.style.width = `${(current / total) * 100}%`;
    elements.passCount.textContent = passCount;
    elements.failCount.textContent = failCount;
}

// Complete execution - stops timer, shows download button
function completeExecution() {
    // Stop timer
    if (executionTimerInterval) {
        clearInterval(executionTimerInterval);
        executionTimerInterval = null;
    }

    // Final time update
    const totalTime = Date.now() - executionStartTime;
    elements.executionTime.textContent = formatDuration(totalTime);

    // Update button and show download
    elements.executeBtn.textContent = '✅ Completed';
    elements.downloadResultsBtn.classList.remove('hidden');

    console.log(`Execution completed in ${formatDuration(totalTime)}`);
}

// Sleep utility
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// =============================================
// IMPORT CUSTOM SCRIPT HANDLING
// =============================================

// Check URL params for auto-open
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('openImport') === 'true' && elements.toggleImportLink) {
    elements.importScriptSection.classList.remove('hidden');
    elements.toggleImportLink.parentElement.classList.add('hidden');

    // Scroll to section
    setTimeout(() => {
        elements.importScriptSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 300); // Small delay to ensure render

    // Clean URL
    window.history.replaceState({}, document.title, window.location.pathname);
}

// Toggle Import Section
if (elements.toggleImportLink) {
    elements.toggleImportLink.addEventListener('click', (e) => {
        e.preventDefault();
        elements.importScriptSection.classList.remove('hidden');
        elements.toggleImportLink.parentElement.classList.add('hidden');
    });
}

// Cancel Import
if (elements.cancelImportBtn) {
    elements.cancelImportBtn.addEventListener('click', () => {
        elements.importScriptSection.classList.add('hidden');
        elements.toggleImportLink.parentElement.classList.remove('hidden');
        // Reset inputs
        elements.importScriptFile.value = '';
        elements.importScriptJson.value = '';
    });
}

// Confirm Import (Upload)
if (elements.confirmImportBtn) {
    elements.confirmImportBtn.addEventListener('click', async () => {
        const file = elements.importScriptFile.files[0];
        const jsonContent = elements.importScriptJson.value.trim();

        if (!file) {
            alert('Please select a Python script file (.py)');
            return;
        }

        if (!jsonContent) {
            alert('Please provide the UI Configuration JSON');
            return;
        }

        // Validate JSON
        try {
            JSON.parse(jsonContent);
        } catch (e) {
            alert('Invalid JSON format in UI Configuration');
            return;
        }

        // Prepare FormData
        const formData = new FormData();
        formData.append('script', file);
        formData.append('config', jsonContent);

        // UI Feedback
        const originalBtnText = elements.confirmImportBtn.textContent;
        elements.confirmImportBtn.disabled = true;
        elements.confirmImportBtn.textContent = 'Uploading...';

        try {
            const response = await fetch('/api/scripts/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok) {
                alert('Script uploaded and registered successfully!');

                // Hide section
                elements.importScriptSection.classList.add('hidden');
                elements.toggleImportLink.parentElement.classList.remove('hidden');

                // Reset inputs
                elements.importScriptFile.value = '';
                elements.importScriptJson.value = '';

                // Reload scripts list
                await loadCustomScripts();

            } else {
                throw new Error(result.error || 'Upload failed');
            }

        } catch (error) {
            console.error('Upload Error:', error);
            alert('Failed to upload script: ' + error.message);
        } finally {
            elements.confirmImportBtn.disabled = false;
            elements.confirmImportBtn.textContent = originalBtnText;
        }
    });
}
// --------------------------------------------------------------------------
// REFACTOR: Dynamic Template Generation
// --------------------------------------------------------------------------
// When a script is selected, we fetch its LIVE metadata to ensure Template is accurate.
async function syncTemplateWithLiveMeta(scriptName) {
    if (!scriptName) return;
    // Ensure .py extension is present
    if (!scriptName.endsWith('.py')) {
        scriptName += '.py';
    }
    try {
        console.log(`[Template Sync] Fetching live metadata for ${scriptName}...`);
        const res = await fetch(`/api/scripts/content?filename=${scriptName}`);
        if (!res.ok) throw new Error("Failed to fetch script content");

        const data = await res.json();
        const meta = data.meta;

        if (meta && (meta.columns || meta.inputColumns || meta.expected_columns)) {
            // Determine best source for columns
            // 1. meta.columns (Full object)
            // 2. meta.inputColumns (Alias)
            // 3. meta.expected_columns (String array -> mapping)

            let cols = meta.columns || meta.inputColumns;

            // If cols is just strings (e.g. expected_columns), convert to objects
            if (!cols && meta.expected_columns) {
                cols = meta.expected_columns.map(c => ({ name: c, type: 'Data', description: 'Auto-detected' }));
            }

            if (cols && cols.length > 0) {
                const currentTemplate = TEMPLATES[scriptName.replace('.py', '')] || TEMPLATES[scriptName];
                if (currentTemplate) {
                    console.log(`[Template Sync] Overriding registry columns with live metadata (${cols.length} cols).`);
                    // Map to template format: { header: 'Name', key: 'Name' }
                    currentTemplate.columns = cols.map(c => ({
                        header: c.name || c,
                        key: c.name || c,
                        width: 20
                    }));

                    // Also sync other config if present
                    if (meta.batchSize) currentTemplate.batchSize = meta.batchSize;
                    if (meta.groupByColumn) currentTemplate.groupByColumn = meta.groupByColumn;
                    if (meta.additionalAttributes) currentTemplate.additionalAttributes = meta.additionalAttributes;
                }
            }
        }
    } catch (e) {
        console.warn("[Template Sync] Failed to sync with live metadata", e);
    }
}
// --------------------------------------------------------------------------

// =============================================
// EXECUTE CUSTOM SCRIPT
// =============================================

// =============================================
// TEMPLATE ACTIONS
// =============================================

// Download Template
if (elements.exportBtn) {
    elements.exportBtn.addEventListener('click', () => {
        if (!selectedDataType) return alert('Please select a script first.');
        const template = TEMPLATES[selectedDataType];
        if (!template) return;

        // Create Excel Template
        let headers = template.columns.map(c => c.header);

        // Add Additional Attributes if enabled
        if (elements.enableAdditionalAttributes && elements.enableAdditionalAttributes.checked) {
            let extraAttrs = [];

            // 1. Prioritize Input Field (User Defined)
            if (elements.additionalAttributesInput && elements.additionalAttributesInput.value.trim()) {
                extraAttrs = elements.additionalAttributesInput.value.split(',').map(s => s.trim()).filter(s => s);
            }
            // 2. Fallback to Template Definition (Legacy)
            else if (template.additionalAttributes) {
                extraAttrs = template.additionalAttributes.map(attr => attr.name || attr);
            }

            if (extraAttrs.length > 0) {
                headers = [...headers, ...extraAttrs];
            }
        }

        const wb = XLSX.utils.book_new();
        const ws = XLSX.utils.json_to_sheet([], { header: headers });

        XLSX.utils.book_append_sheet(wb, ws, 'Template');
        XLSX.writeFile(wb, `${template.name}_Template.xlsx`);
    });
}

// Import Template (Trigger File Upload)
if (elements.importBtn) {
    elements.importBtn.textContent = 'Login and Import Template';
    elements.importBtn.addEventListener('click', () => {
        if (!selectedDataType) return alert('Please select a script first.');

        // Show Login/Upload Section Logic
        if (elements.loginSection) {
            elements.loginSection.classList.remove('hidden');
            elements.loginSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        if (elements.fileUpload) {
            // Auto-trigger removed as per user request
        }
    });
}


// =============================================
// LOGIN COMPONENT INITIALIZATION
// =============================================

document.addEventListener('DOMContentLoaded', () => {
    // 1. Clear Session on Reload (as per logic seen in v2) or keep?
    // User often wants fresh start or specific behavior.
    // Let's implement standard init.

    // Check if LoginComponent is defined (from global script)
    if (typeof LoginComponent !== 'undefined') {
        loginComponent = new LoginComponent('login-component-container', {
            apiEndpoint: '/api/user-aggregate/token', // Standard endpoint
            onLoginSuccess: (token, userDetails) => {
                authToken = token;
                currentEnvironment = userDetails.environment;
                currentTenant = userDetails.tenant;

                // Update Session UI
                if (elements.loginFormContainer) elements.loginFormContainer.classList.add('hidden');
                if (elements.sessionContainer) elements.sessionContainer.classList.remove('hidden');
                if (elements.uploadWorkflowContainer) {
                    elements.uploadWorkflowContainer.classList.remove('disabled-area');
                    elements.uploadWorkflowContainer.style.opacity = '1';
                    elements.uploadWorkflowContainer.style.pointerEvents = 'auto';
                }

                if (elements.sessionInfo) {
                    elements.sessionInfo.textContent = `${userDetails.username} (${userDetails.tenant}) [${userDetails.environment}]`;
                }

                // If Environment selected, load refs
                // loadAssetReferenceData(); 
            },
            onLogout: () => {
                fullLogout();
            }
        });
    } else {
        console.error('LoginComponent class not found. Ensure login_component.js is loaded.');
    }

    // Logout Hook

});


// =============================================
// EXECUTE SCRIPT LOGIC (RESTORED)
// =============================================

if (elements.executeBtn) {
    elements.executeBtn.addEventListener('click', async () => {
        if (!selectedDataType) return alert('Please select a script first.');
        if (!authToken) return alert('Please login first.');

        // 1. Get Rows from Excel
        const fileInput = elements.fileUpload;
        if (!fileInput.files.length) return alert('Please upload a filled template.');

        const file = fileInput.files[0];
        const reader = new FileReader();

        reader.onload = async (e) => {
            try {
                const data = new Uint8Array(e.target.result);
                const workbook = XLSX.read(data, { type: 'array' });
                const firstSheetName = workbook.SheetNames[0];
                const worksheet = workbook.Sheets[firstSheetName];
                const rows = XLSX.utils.sheet_to_json(worksheet);

                if (rows.length === 0) return alert('Excel file is empty.');

                // 2. Start Execution
                const stats = startExecution();
                const total = rows.length;
                let processed = 0;
                let pass = 0;
                let fail = 0;

                // [BATCHING LOGIC START]
                // Retrieve batchSize from template or default to 10
                const template = TEMPLATES[selectedDataType] || {};
                // Ensure batchSize is a valid number > 0
                let batchSize = parseInt(template.batchSize);
                if (isNaN(batchSize) || batchSize <= 0) batchSize = 10;

                console.log(`[Execute] Total Rows: ${total}, Batch Size: ${batchSize}`);

                executionResults = []; // Initialize accumulator
                updateProgress(0, total, 0, 0);

                // Get Env Config
                const envData = getEnvUrls(currentEnvironment);
                const apiBaseUrl = envData.apiBaseUrl;

                const config = {
                    environment: currentEnvironment,
                    tenant: currentTenant,
                    apiurl: apiBaseUrl, // Critical for scripts
                    apiBaseUrl: apiBaseUrl, // Also critical for converted scripts expecting this key
                    google_api_key: (typeof tagRefData !== 'undefined' && tagRefData.google_api_key) ? tagRefData.google_api_key : "",
                    boundary: {
                        minLat: elements.minLat ? elements.minLat.value : '',
                        maxLat: elements.maxLat ? elements.maxLat.value : '',
                        minLong: elements.minLong ? elements.minLong.value : '',
                        maxLong: elements.maxLong ? elements.maxLong.value : '',
                        locationName: elements.locationName ? elements.locationName.value : ''
                    },
                    targetLocation: (elements.v2LocationName && elements.v2LocationName.value) ? elements.v2LocationName.value : (document.getElementById('target-location-input') ? document.getElementById('target-location-input').value : ""),
                    area_size: (elements.v2AreaSize && !elements.v2SpecificConfig.classList.contains('hidden')) ? elements.v2AreaSize.value : undefined,
                    area_unit: (elements.v2AreaUnit && !elements.v2SpecificConfig.classList.contains('hidden')) ? elements.v2AreaUnit.value : undefined,
                    allowAdditionalAttributes: elements.enableAdditionalAttributes ? elements.enableAdditionalAttributes.checked : false,
                    additionalAttributes: (elements.enableAdditionalAttributes && elements.enableAdditionalAttributes.checked)
                        ? (elements.additionalAttributesInput && elements.additionalAttributesInput.value ? elements.additionalAttributesInput.value.split(',').map(s => s.trim()).filter(k => k) : [])
                        : []
                };

                try {
                    const scriptFilename = template.filename || selectedDataType;

                    // [V2 ROUTING]
                    const LEGACY_SCRIPTS = ['Area_Audit', 'Area Audit', 'Area_Audit.py'];
                    const isLegacy = LEGACY_SCRIPTS.some(n => selectedDataType.includes(n)) || (template.isLegacy);
                    const useV2 = !isLegacy && typeof ScriptExecutorV2 !== 'undefined';

                    if (useV2) {
                        // [V2 UPDATE] Additional Attributes Logic
                        if (elements.additionalAttributesInput && elements.additionalAttributesInput.value.trim()) {
                            const keysToManage = elements.additionalAttributesInput.value.split(',').map(s => s.trim()).filter(k => k);
                            const isEnabled = elements.enableAdditionalAttributes && elements.enableAdditionalAttributes.checked;

                            if (!isEnabled) {
                                console.log("[Execute] Stripping Additional Attributes (Disabled):", keysToManage);
                                rows.forEach(row => {
                                    keysToManage.forEach(k => {
                                        delete row[k];
                                    });
                                });
                            } else {
                                console.log("[Execute] Allowing Additional Attributes (Enabled):", keysToManage);
                            }
                        }
                    }

                    // [GROUPING & BATCHING LOGIC]
                    // 1. Pre-process rows into "Execution Units".
                    //    - If Grouping: One Unit = Array of rows belonging to one key.
                    //    - If No Grouping: One Unit = Single Row.

                    let executionUnits = [];
                    const groupByCol = template.groupByColumn;

                    if (groupByCol && groupByCol.trim()) {
                        console.log(`[Execute] Grouping by column: '${groupByCol}'`);

                        // Group rows efficiently
                        const groups = new Map();
                        rows.forEach(row => {
                            const key = row[groupByCol] || 'UNK';
                            if (!groups.has(key)) groups.set(key, []);
                            groups.get(key).push(row);
                        });

                        // Convert Map values to Units (Array of Arrays)
                        executionUnits = Array.from(groups.values());
                        console.log(`[Execute] Formed ${executionUnits.length} Groups from ${rows.length} Rows.`);

                    } else {
                        // No grouping, each row is a unit
                        executionUnits = rows;
                    }

                    // 2. Form Batches from Units
                    // We must NOT split a Unit across batches.
                    // However, if a single Unit is larger than batchSize, it must stand alone in a batch (or overflow).

                    const batches = [];
                    let currentBatch = [];
                    let currentBatchSize = 0;

                    for (const unit of executionUnits) {
                        const unitRows = Array.isArray(unit) ? unit : [unit];
                        const unitSize = unitRows.length;

                        // If adding this unit exceeds batchSize AND we already have data, push current batch
                        if (currentBatchSize + unitSize > batchSize && currentBatchSize > 0) {
                            batches.push(currentBatch);
                            currentBatch = [];
                            currentBatchSize = 0;
                        }

                        // Add unit to current batch
                        currentBatch = currentBatch.concat(unitRows);
                        currentBatchSize += unitSize;
                    }
                    if (currentBatch.length > 0) batches.push(currentBatch);

                    console.log(`[Execute] Prepared ${batches.length} Batches for execution.`);

                    // 3. Process Batches
                    for (let i = 0; i < batches.length; i++) {
                        const chunk = batches[i];
                        console.log(`[Execute] Processing Batch ${i + 1}/${batches.length} (${chunk.length} rows)`);

                        let chunkResults = [];

                        if (useV2) {
                            // Call V2 Executor for Chunk
                            const executor = new ScriptExecutorV2({ apiBaseUrl: apiBaseUrl, debug: false });
                            chunkResults = await executor.execute(scriptFilename, chunk, authToken, config, config.boundary);
                        } else {
                            // Call Legacy Endpoint for Chunk
                            const response = await fetch('/api/scripts/execute', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    scriptName: scriptFilename,
                                    rows: chunk,
                                    token: authToken,
                                    envConfig: config
                                })
                            });

                            if (!response.ok) {
                                const err = await response.json();
                                chunkResults = chunk.map(r => ({ ...r, status: 'Error', response: err.error || 'Batch Execution Failed' }));
                            } else {
                                chunkResults = await response.json();
                            }
                        }

                        // Accumulate Results
                        executionResults = executionResults.concat(chunkResults);

                        // Update Progress immediately
                        const chunkPass = chunkResults.filter(r => {
                            const s = String(r.status || r.Status || '').toLowerCase();
                            return s === 'success' || s === 'pass' || s === 'passed';
                        }).length;
                        const chunkFail = chunkResults.length - chunkPass;

                        pass += chunkPass;
                        fail += chunkFail;
                        processed += chunk.length;

                        renderExecutionResults();
                        updateProgress(processed, total, pass, fail);

                        // Small delay to allow UI to breathe
                        await new Promise(r => setTimeout(r, 50));
                    }


                } catch (error) {
                    console.error('Execution Critical Failure:', error);
                    alert('Execution Interrupted: ' + error.message);
                } finally {
                    completeExecution();
                }

            } catch (readErr) {
                console.error('File Read Error:', readErr);
                alert('Failed to read Excel file.');
                completeExecution();
            }
        };
        reader.readAsArrayBuffer(file);
    });
}

// =============================================
// AREA AUDIT V2 LOGIC
// =============================================
if (elements.v2ResolveBtn) {
    console.log("[Init] V2 Resolve Button Found");
    elements.v2ResolveBtn.addEventListener('click', async () => {
        console.log("[V2] Resolve Clicked");
        const locName = elements.v2LocationName.value.trim();
        if (!locName) return alert("Please enter a location name.");

        const btn = elements.v2ResolveBtn;
        const originalText = btn.innerText;
        btn.innerText = "⏳";
        btn.disabled = true;

        try {
            // Use Backend Proxy (Server-Side Geocoding)
            // This avoids loading the heavy Google Maps Client Library
            const response = await fetch('/api/geocode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ address: locName })
            });

            const data = await response.json();

            btn.innerText = "📍 Resolve";
            btn.disabled = false;

            // Handle Proxy Response (Single Object with geometry) OR Raw Google Response (Array)
            const geometry = data.geometry || (data.results && data.results[0] ? data.results[0].geometry : null);

            if (geometry) {
                console.log("[V2] Geocode Success:", data);

                const bounds = geometry.bounds;
                const viewport = geometry.viewport;
                const finalBounds = bounds || viewport;

                if (finalBounds) {
                    // Google API returns { northeast: {lat, lng}, southwest: {lat, lng} }
                    const ne = finalBounds.northeast;
                    const sw = finalBounds.southwest;

                    elements.maxLat.value = ne.lat;
                    elements.maxLong.value = ne.lng;
                    elements.minLat.value = sw.lat;
                    elements.minLong.value = sw.lng;

                    if (elements.boundaryConfig) elements.boundaryConfig.classList.remove('hidden');
                } else {
                    alert("Location found, but no boundary bounds returned.");
                }
            } else {
                console.error("[V2] Geocode Failed:", data);
                // Try to extract error message from raw google error if passed through
                const errMsg = data.error_message || data.status || (data.error ? data.error : 'Unknown error');
                alert('Geocode failed: ' + errMsg);
            }

        } catch (e) {
            console.error("[V2] Error resolving boundary", e);
            alert("Error resolving boundary: " + e.message);
            btn.innerText = originalText;
            btn.disabled = false;
        }
    });
} else {
    console.warn("[Init] V2 Resolve Button NOT Found");
}




