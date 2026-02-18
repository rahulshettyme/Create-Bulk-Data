const https = require('https');
const fs = require('fs');
const path = require('path');
const multer = require('multer');
const { spawn } = require('child_process');

const QA_TOKEN_BASE = "https://v2sso-gcp.cropin.co.in/auth/realms/";
const PROD_TOKEN_BASE = "https://sso.sg.cropin.in/auth/realms/";
const DB_FILE = path.join(__dirname, '..', 'System', 'db.json');

// Helper to read DB
const readDb = () => {
    try {
        const data = fs.readFileSync(DB_FILE, 'utf8');
        const json = JSON.parse(data);
        if (!json.jiraTokens) json.jiraTokens = [];
        if (!json.savedLocations) json.savedLocations = [];
        return json;
    } catch (err) {
        return { users: [], jiraTokens: [], savedLocations: [], environment_urls: {}, gemini_api_key: "" };
    }
};

// Initialize API Key from DB or Environment
const SECRETS_FILE = path.join(__dirname, '..', 'System', 'secrets.json');

// Helper to read Secrets
const readSecrets = () => {
    try {
        if (fs.existsSync(SECRETS_FILE)) {
            const data = fs.readFileSync(SECRETS_FILE, 'utf8');
            return JSON.parse(data);
        }
    } catch (err) {
        console.error('Error reading secrets:', err);
    }
    return {};
};

// Initialize API Key from Environment > Secrets File > DB File (Legacy)
const dbData = readDb();
const secretsData = readSecrets();
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || secretsData.google_api_key || secretsData.gemini_api_key || dbData.google_api_key || dbData.gemini_api_key || "";
// Specific Key for Geocoding (User Request)
const GEOCODING_API_KEY = process.env.Geocoding_api_key || process.env.GEOCODING_API_KEY || secretsData.Geocoding_api_key || GOOGLE_API_KEY;


// Helper to write DB
const writeDb = (data) => {
    try {
        fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
    } catch (err) {
        console.error('Error writing DB:', err);
    }
};

function getEnvUrls(environment) {
    const db = readDb();
    const envApiUrls = db.environment_api_urls || {};
    const envUrls = db.environment_urls || {};
    const ssoConfig = db.sso_config || {};

    let apiBaseUrl = null; // Default null
    let frontendUrl = null;
    let ssoPrefix = null;
    let ssoSuffix = ssoConfig.suffix || '/protocol/openid-connect/token';

    if (environment) {
        // Determine SSO Prefix
        if (environment.toLowerCase().startsWith('qa')) {
            ssoPrefix = ssoConfig.qa_prefix || "https://v2sso-gcp.cropin.co.in/auth/realms/";
        } else {
            ssoPrefix = ssoConfig.prod_prefix || "https://sso.sg.cropin.in/auth/realms/";
        }

        for (const key of Object.keys(envApiUrls)) {
            if (key.toLowerCase() === environment.toLowerCase()) {
                apiBaseUrl = envApiUrls[key];
                break;
            }
        }
        for (const key of Object.keys(envUrls)) {
            if (key.toLowerCase() === environment.toLowerCase()) {
                frontendUrl = envUrls[key];
                break;
            }
        }
    }
    return { apiBaseUrl, frontendUrl, ssoPrefix, ssoSuffix };
}

// Helper for GET requests
function handleGetRequest(req, res, pathSuffix, logPrefix) {
    const { environment, tenant } = req.query;
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({ error: 'Missing token' });
    }

    const { apiBaseUrl, frontendUrl } = getEnvUrls(environment);
    if (!apiBaseUrl) {
        return res.status(400).json({ error: `Unknown environment: ${environment}` });
    }

    const fullUrl = `${apiBaseUrl}${pathSuffix}`;

    const urlObj = new URL(fullUrl);
    const options = {
        hostname: urlObj.hostname,
        port: 443,
        path: urlObj.pathname + urlObj.search,
        method: 'GET',
        headers: {
            'Authorization': authHeader,
            'Accept': 'application/json',
            'origin': frontendUrl || apiBaseUrl,
            'referer': (frontendUrl || apiBaseUrl) + '/'
        }
    };

    const proxyReq = https.request(options, (proxyRes) => {
        let data = '';
        proxyRes.on('data', chunk => data += chunk);
        proxyRes.on('end', () => {
            if (proxyRes.statusCode >= 200 && proxyRes.statusCode < 300) {
                try {
                    res.json(JSON.parse(data));
                } catch (e) {
                    res.status(500).json({ error: 'Failed to parse response' });
                }
            } else {
                res.status(proxyRes.statusCode).json({ error: 'Upstream error' });
            }
        });
    });

    proxyReq.on('error', (e) => {
        res.status(500).json({ error: 'Request failed: ' + e.message });
    });
    proxyReq.end();
}

module.exports = function (app) {
    // POST /api/geocode - Get address components from Google Geocoding API
    app.post('/api/geocode', async (req, res) => {
        const { address, lat, lng } = req.body;

        let geocodeUrl;
        if (address) {
            geocodeUrl = `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(address)}&key=${GEOCODING_API_KEY}`;
        } else if (lat !== undefined && lng !== undefined) {
            geocodeUrl = `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=${GEOCODING_API_KEY}`;
        } else {
            return res.status(400).json({ error: 'Missing address or lat/lng parameters' });
        }

        try {
            const urlObj = new URL(geocodeUrl);

            const options = {
                hostname: urlObj.hostname,
                port: 443,
                path: urlObj.pathname + urlObj.search,
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                }
            };

            const geoReq = https.request(options, (geoRes) => {
                let data = '';

                geoRes.on('data', (chunk) => {
                    data += chunk;
                });

                geoRes.on('end', () => {
                    console.log(`[Geocode Proxy] Status: ${geoRes.statusCode}`);
                    try {
                        const jsonData = JSON.parse(data);

                        if (geoRes.statusCode !== 200 || !jsonData.results || jsonData.results.length === 0) {
                            console.warn('[Geocode Proxy] Failed or Empty:', JSON.stringify(jsonData));
                            // Return raw error or empty to help debug
                            return res.json(jsonData);
                        }

                        const result = jsonData.results[0];
                        const addressComponents = result.address_components || [];

                        const getComponent = (types) => {
                            for (const comp of addressComponents) {
                                if (types.some(t => comp.types.includes(t))) {
                                    return comp.long_name || '';
                                }
                            }
                            return '';
                        };

                        const geometry = result.geometry?.location || {};
                        const latitude = geometry.lat || lat;
                        const longitude = geometry.lng || lng;

                        const addressResult = {
                            country: getComponent(['country']),
                            formattedAddress: result.formatted_address || '',
                            administrativeAreaLevel1: getComponent(['administrative_area_level_1']),
                            administrativeAreaLevel2: getComponent(['administrative_area_level_2']),
                            locality: getComponent(['locality']),
                            sublocalityLevel1: getComponent(['sublocality_level_1']),
                            sublocalityLevel2: getComponent(['sublocality_level_2']),
                            landmark: '',
                            postalCode: getComponent(['postal_code']),
                            houseNo: '',
                            buildingName: '',
                            placeId: result.place_id || '',
                            latitude: latitude,
                            longitude: longitude,
                            geometry: result.geometry // Include full geometry for bounds/viewport
                        };

                        res.json(addressResult);

                    } catch (e) {
                        console.error('[Geocode] Parse Error:', e);
                        res.json({});
                    }
                });
            });

            geoReq.on('error', (e) => {
                console.error('[Geocode] Request Error:', e);
                res.json({});
            });

            geoReq.end();

        } catch (err) {
            console.error('[Geocode] Error:', err);
            res.json({});
        }
    });

    // POST /api/data-generate/create-farmer - Create a farmer via API
    app.post('/api/data-generate/create-farmer', async (req, res) => {
        const { environment, tenant, farmer } = req.body;
        const authHeader = req.headers.authorization;

        if (!environment || !farmer) {
            return res.status(400).json({ error: 'Missing environment or farmer data' });
        }

        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return res.status(401).json({ error: 'Missing or invalid authorization header' });
        }

        const { apiBaseUrl, frontendUrl } = getEnvUrls(environment);

        if (!apiBaseUrl) {
            return res.status(400).json({ error: `Unknown environment: ${environment}` });
        }

        const farmerUrl = `${apiBaseUrl}/services/farm/api/farmers`;
        console.log(`[Create Farmer] URL: ${farmerUrl}`);

        try {
            const urlObj = new URL(farmerUrl);

            // Create form-data payload (key=dto)
            const jsonData = JSON.stringify(farmer);
            const boundary = '----FormBoundary' + Math.random().toString(16).substr(2);

            let formBody = '';
            formBody += `--${boundary}\r\n`;
            formBody += `Content-Disposition: form-data; name="dto"; filename="body.json"\r\n`;
            formBody += `Content-Type: application/json\r\n\r\n`;
            formBody += jsonData + '\r\n';
            formBody += `--${boundary}--\r\n`;

            const options = {
                hostname: urlObj.hostname,
                port: 443,
                path: urlObj.pathname,
                method: 'POST',
                headers: {
                    'Authorization': authHeader,
                    'Accept': 'application/json, text/plain, */*',
                    'Content-Type': `multipart/form-data; boundary=${boundary}`,
                    'Content-Length': Buffer.byteLength(formBody),
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'origin': frontendUrl || apiBaseUrl,
                    'referer': (frontendUrl || apiBaseUrl) + '/'
                }
            };

            const farmerReq = https.request(options, (farmerRes) => {
                let data = '';

                farmerRes.on('data', (chunk) => {
                    data += chunk;
                });

                farmerRes.on('end', () => {
                    console.log(`[Create Farmer] Response Status: ${farmerRes.statusCode}`);

                    try {
                        const jsonResponse = data ? JSON.parse(data) : {};
                        res.status(farmerRes.statusCode).json(jsonResponse);
                    } catch (e) {
                        res.status(farmerRes.statusCode).json({
                            message: data.substring(0, 200),
                            statusCode: farmerRes.statusCode
                        });
                    }
                });
            });

            farmerReq.on('error', (e) => {
                console.error('[Create Farmer] Request Error:', e);
                res.status(500).json({ error: 'Farmer creation request failed: ' + e.message });
            });

            farmerReq.write(formBody);
            farmerReq.end();

        } catch (err) {
            console.error('[Create Farmer] Error:', err);
            res.status(500).json({ error: 'Internal error: ' + err.message });
        }
    });

    // GET /api/data-generate/farmers-list
    app.get('/api/data-generate/farmers-list', (req, res) => {
        handleGetRequest(req, res, '/services/farm/api/farmers/dropdownList', '[Farmers List]');
    });

    // GET /api/data-generate/soil-types
    app.get('/api/data-generate/soil-types', (req, res) => {
        handleGetRequest(req, res, '/services/farm/api/soil-types', '[Soil Types]');
    });

    // GET /api/data-generate/irrigation-types
    app.get('/api/data-generate/irrigation-types', (req, res) => {
        handleGetRequest(req, res, '/services/farm/api/irrigation-types', '[Irrigation Types]');
    });

    // POST /api/data-generate/create-asset
    app.post('/api/data-generate/create-asset', async (req, res) => {
        const { environment, tenant, asset } = req.body;
        const authHeader = req.headers.authorization;

        if (!environment || !asset) {
            return res.status(400).json({ error: 'Missing environment or asset data' });
        }

        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return res.status(401).json({ error: 'Missing or invalid authorization header' });
        }

        const { apiBaseUrl, frontendUrl } = getEnvUrls(environment);
        if (!apiBaseUrl) {
            return res.status(400).json({ error: `Unknown environment: ${environment}` });
        }

        const assetUrl = `${apiBaseUrl}/services/farm/api/assets`;
        console.log(`[Create Asset] URL: ${assetUrl}`);

        try {
            const urlObj = new URL(assetUrl);
            const jsonData = JSON.stringify(asset);
            const boundary = '----FormBoundary' + Math.random().toString(16).substr(2);

            let formBody = '';
            formBody += `--${boundary}\r\n`;
            formBody += `Content-Disposition: form-data; name="dto"; filename="body.json"\r\n`;
            formBody += `Content-Type: application/json\r\n\r\n`;
            formBody += jsonData + '\r\n';
            formBody += `--${boundary}--\r\n`;

            const options = {
                hostname: urlObj.hostname,
                port: 443,
                path: urlObj.pathname,
                method: 'POST',
                headers: {
                    'Authorization': authHeader,
                    'Accept': 'application/json, text/plain, */*',
                    'Content-Type': `multipart/form-data; boundary=${boundary}`,
                    'Content-Length': Buffer.byteLength(formBody),
                    'User-Agent': 'Mozilla/5.0',
                    'origin': frontendUrl || apiBaseUrl,
                    'referer': (frontendUrl || apiBaseUrl) + '/'
                }
            };

            const assetReq = https.request(options, (assetRes) => {
                let data = '';
                assetRes.on('data', chunk => data += chunk);
                assetRes.on('end', () => {
                    console.log(`[Create Asset] Status: ${assetRes.statusCode}`);
                    try {
                        const jsonResponse = data ? JSON.parse(data) : {};
                        res.status(assetRes.statusCode).json(jsonResponse);
                    } catch (e) {
                        res.status(assetRes.statusCode).json({
                            message: data.substring(0, 200),
                            statusCode: assetRes.statusCode
                        });
                    }
                });
            });

            assetReq.on('error', (e) => {
                console.error('[Create Asset] Request Error:', e);
                res.status(500).json({ error: 'Asset creation failed: ' + e.message });
            });

            assetReq.write(formBody);
            assetReq.end();

        } catch (err) {
            console.error('[Create Asset] Error:', err);
            res.status(500).json({ error: 'Internal error: ' + err.message });
        }
    });

    // GET /api/data-generate/master-tags - Get Master Tags (Type=FARMER)
    app.get('/api/data-generate/master-tags', (req, res) => {
        handleGetRequest(req, res, '/services/master/api/filter?type=FARMER', '[Master Tags]');
    });

    // GET /api/data-generate/farmer-details - Get specific farmer details
    app.get('/api/data-generate/farmer-details', (req, res) => {
        const { id, environment, tenant } = req.query;
        if (!id) return res.status(400).json({ error: 'Missing farmer ID' });
        // handleGetRequest expects environment/tenant in query, which we have.
        // pathSuffix needs the ID.
        handleGetRequest(req, res, `/services/farm/api/farmers/${id}`, `[Get Farmer ${id}]`);
    });

    // GET /api/data-generate/company-config - Get Company Config (Hardcoded ID 1251)
    app.get('/api/data-generate/company-config', (req, res) => {
        handleGetRequest(req, res, '/services/farm/api/companies/1251', '[Company Config]');
    });

    // GET /api/data-generate/user-info - Get User Info
    app.get('/api/data-generate/user-info', (req, res) => {
        handleGetRequest(req, res, '/services/user/api/users/user-info', '[User Info]');
    });

    // PUT /api/data-generate/update-farmer - Update farmer (specifically for tags)
    app.put('/api/data-generate/update-farmer', async (req, res) => {
        const { environment, tenant, farmer } = req.body;
        const authHeader = req.headers.authorization;

        if (!environment || !farmer) {
            return res.status(400).json({ error: 'Missing environment or farmer data' });
        }

        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return res.status(401).json({ error: 'Missing or invalid authorization header' });
        }

        // Resolve URL
        const { apiBaseUrl, frontendUrl } = getEnvUrls(environment);
        if (!apiBaseUrl) {
            return res.status(400).json({ error: `Unknown environment: ${environment}` });
        }

        const farmerUrl = `${apiBaseUrl}/services/farm/api/farmers`;

        try {
            const boundary = '----WebKitFormBoundary' + Math.random().toString(36).substring(2);

            // Construct Multipart Body (DTO only)
            let formBody = '';
            formBody += `--${boundary}\r\n`;
            formBody += 'Content-Disposition: form-data; name="dto"; filename="body.json"\r\n';
            formBody += 'Content-Type: application/json\r\n\r\n';
            formBody += JSON.stringify(farmer) + '\r\n';
            formBody += `--${boundary}--\r\n`;

            const urlObj = new URL(farmerUrl);
            const options = {
                hostname: urlObj.hostname,
                port: 443,
                path: urlObj.pathname,
                method: 'PUT',
                headers: {
                    'Authorization': authHeader,
                    'Accept': 'application/json, text/plain, */*',
                    'Content-Type': `multipart/form-data; boundary=${boundary}`,
                    'Content-Length': Buffer.byteLength(formBody),
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'origin': frontendUrl || apiBaseUrl,
                    'referer': (frontendUrl || apiBaseUrl) + '/'
                }
            };

            const updateReq = https.request(options, (updateRes) => {
                let data = '';
                updateRes.on('data', chunk => data += chunk);
                updateRes.on('end', () => {
                    if (updateRes.statusCode >= 200 && updateRes.statusCode < 300) {
                        try {
                            const json = JSON.parse(data);
                            res.json(json);
                        } catch (e) {
                            // Sometimes PUT returns empty body or just status
                            res.json({ status: 'Success', message: 'Farmer updated' });
                        }
                    } else {
                        res.status(updateRes.statusCode).json({ error: `Update failed with status ${updateRes.statusCode}`, details: data });
                    }
                });
            });

            updateReq.on('error', (e) => {
                res.status(500).json({ error: 'Update request failed: ' + e.message });
            });

            updateReq.write(formBody);
            updateReq.end();

        } catch (e) {
            console.error('[Update Farmer] Error:', e);
            res.status(500).json({ error: 'Internal server error' });
        }
    });

    // POST /api/data-generate/area-audit - Process area audit for a Croppable Area
    app.post('/api/data-generate/area-audit', async (req, res) => {
        const { environment, tenant, caId, coordinates } = req.body;
        const authHeader = req.headers.authorization;

        if (!environment || !caId || !coordinates) {
            return res.status(400).json({ error: 'Missing environment, caId, or coordinates' });
        }

        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return res.status(401).json({ error: 'Missing or invalid authorization header' });
        }

        // Get environment API URL from db.json
        const { apiBaseUrl, frontendUrl } = getEnvUrls(environment);

        if (!apiBaseUrl) {
            return res.status(400).json({ error: `Unknown environment: ${environment}` });
        }

        const geoAreaUrl = `${apiBaseUrl}/services/utilservice/api/geojson/area`;
        const putCAUrl = `${apiBaseUrl}/services/farm/api/croppable-areas/area-audit`;
        const userInfoUrl = `${apiBaseUrl}/services/user/api/users/user-info`;

        console.log(`[Area Audit] Processing CA ID: ${caId}`);

        try {
            // Build GeoJSON payload for geo area API
            const geoPayload = {
                type: "FeatureCollection",
                features: [{
                    type: "Feature",
                    properties: {},
                    geometry: {
                        coordinates: coordinates,
                        type: "MultiPolygon"
                    }
                }]
            };

            // Helper function to make HTTPS request as Promise
            const makeRequest = (url, method, body = null) => {
                return new Promise((resolve, reject) => {
                    const urlObj = new URL(url);
                    const postData = body ? JSON.stringify(body) : null;

                    const headers = {
                        'Authorization': authHeader,
                        'Accept': 'application/json',
                        'Content-Type': 'application/json',
                        'User-Agent': 'Mozilla/5.0',
                        'origin': frontendUrl || apiBaseUrl,
                        'referer': (frontendUrl || apiBaseUrl) + '/'
                    };

                    if (postData) {
                        headers['Content-Length'] = Buffer.byteLength(postData);
                    }

                    const options = {
                        hostname: urlObj.hostname,
                        port: 443,
                        path: urlObj.pathname + urlObj.search,
                        method: method,
                        headers: headers
                    };

                    const req = https.request(options, (response) => {
                        let data = '';
                        response.on('data', chunk => data += chunk);
                        response.on('end', () => {
                            try {
                                const json = data ? JSON.parse(data) : {};
                                resolve({ status: response.statusCode, data: json });
                            } catch (e) {
                                resolve({ status: response.statusCode, data: { raw: data } });
                            }
                        });
                    });

                    req.on('error', reject);
                    if (postData) req.write(postData);
                    req.end();
                });
            };




            // Step 1: Call Geo Area API
            console.log(`[Area Audit] Calling GeoAPI: ${geoAreaUrl}`);
            const geoResult = await makeRequest(geoAreaUrl, 'POST', geoPayload);

            if (geoResult.status !== 200) {
                return res.status(geoResult.status).json({
                    success: false,
                    error: `GeoAPI failed: ${JSON.stringify(geoResult.data)}`
                });
            }

            const geoData = geoResult.data;
            const latitude = geoData.latitude;
            const longitude = geoData.longitude;
            let auditedArea = parseFloat(geoData.auditedArea); // Already in acres from API
            const geoInfo = geoPayload;

            // Apply Conversion if factor provided
            const conversionFactor = parseFloat(req.body.conversionFactor);
            if (!isNaN(conversionFactor) && conversionFactor > 0) {
                console.log(`[Area Audit] Converting Area: ${auditedArea} * ${conversionFactor}`);
                auditedArea = auditedArea * conversionFactor;
            }

            console.log(`[Area Audit] GeoAPI result: Area=${auditedArea}, Lat=${latitude}, Lon=${longitude}`);

            // Step 2: Build and send CA update payload
            const caPayload = {
                id: parseInt(caId),
                cropAudited: true,
                latitude: parseFloat(latitude),
                longitude: parseFloat(longitude),
                auditedArea: { count: auditedArea },
                usableArea: { count: auditedArea },
                areaAudit: {
                    geoInfo: geoInfo,
                    latitude: parseFloat(latitude),
                    longitude: parseFloat(longitude),
                    channel: "mobile"
                }
            };

            console.log(`[Area Audit] Updating CA: ${putCAUrl}`);
            const caResult = await makeRequest(putCAUrl, 'PUT', caPayload);

            if (caResult.status === 200) {
                res.json({
                    success: true,
                    message: 'Area audit completed successfully',
                    auditedArea: auditedArea,
                    latitude: latitude,
                    longitude: longitude,
                    geoInfo: geoInfo
                });
            } else {
                res.status(caResult.status).json({
                    success: false,
                    error: caResult.data.title || caResult.data.message || 'CA update failed',
                    details: caResult.data
                });
            }

        } catch (err) {
            console.error('[Area Audit] Error:', err);
            res.status(500).json({ success: false, error: 'Internal error: ' + err.message });
        }
    });


    // 2. GET ENVIRONMENT CONFIG
    app.get('/api/env-urls', (req, res) => {
        const db = readDb();
        res.json({
            environment_api_urls: db.environment_api_urls || {},
            environment_urls: db.environment_urls || {}
        });
    });

    // GET /api/saved-locations
    app.get('/api/saved-locations', (req, res) => {
        const db = readDb();
        res.json(db.savedLocations || []);
    });

    // POST /api/saved-locations
    app.post('/api/saved-locations', (req, res) => {
        const locations = req.body;
        if (!Array.isArray(locations)) {
            return res.status(400).json({ error: 'Expected array of locations' });
        }
        const db = readDb();
        db.savedLocations = locations;
        writeDb(db);
        res.json({ success: true });
    });

    // --- Bulk Data Manager Endpoints ---

    // 1. List Custom Scripts
    // 1. List Custom Scripts
    app.get('/api/scripts/custom', (req, res) => {
        const registryPath = path.join(__dirname, '..', 'System', 'scripts_registry.json');

        if (fs.existsSync(registryPath)) {
            try {
                const registryContent = fs.readFileSync(registryPath, 'utf8');
                let scripts = JSON.parse(registryContent);

                // FILTER SYSTEM FILES (BLACKLIST)
                const SYSTEM_FILES = [
                    'thread_utils.py',
                    'attribute_utils.py',
                    'algorithm_utils.py',
                    'DraftTest.py',
                    'TestScript.py'
                ];

                scripts = scripts.filter(s => {
                    const fname = s.filename || s.name;
                    return !SYSTEM_FILES.includes(fname);
                });

                return res.json(scripts);
            } catch (e) {
                console.error('Error reading registry:', e);
                return res.status(500).json({ error: 'Failed to read script registry' });
            }
        } else {
            return res.json([]);
        }
    });

    // 2. Execute Python Script
    // --- Config Endpoints ---
    app.get('/api/config/maps-key', (req, res) => {
        if (GOOGLE_API_KEY) {
            res.json({ key: GOOGLE_API_KEY });
        } else {
            res.status(404).json({ error: "No API Key configured" });
        }
    });

    // 1. Execute Script
    app.post('/api/scripts/execute', async (req, res) => {
        // Clear console for fresh logs per execution
        console.clear();
        console.log('\n--- NEW SCRIPT EXECUTION STARTED ---\n');

        const { scriptName, rows, token, envConfig } = req.body;

        if (!scriptName || !rows || !token) {
            return res.status(400).json({ error: 'Missing required parameters' });
        }

        // [Fix for Parity with Test Run] Inject apiBaseUrl if missing
        if (envConfig && envConfig.environment) {
            console.log(`[Execute] Resolving URL for env: ${envConfig.environment}`);
            const { apiBaseUrl } = getEnvUrls(envConfig.environment);
            if (apiBaseUrl) {
                envConfig.apiBaseUrl = apiBaseUrl;
                // Also ensure 'apiurl' is set as some legacy scripts use this
                if (!envConfig.apiurl) envConfig.apiurl = apiBaseUrl;
            }
        }

        // Locate the script
        // UPDATED: Runnable scripts are now in 'Converted Scripts' sibling folder
        const scriptPath = path.join(__dirname, '..', 'Converted Scripts', scriptName);
        const bridgePath = path.join(__dirname, '..', 'Manager', 'runner_bridge.py');

        console.log(`[Execute] Looking for script at: ${scriptPath}`);
        if (!fs.existsSync(scriptPath)) {
            console.error(`[Execute] Script NOT FOUND at: ${scriptPath}`);
            return res.status(404).json({ error: 'Script file not found' });
        }

        // LOAD COLUMNS FROM REGISTRY (Fallback to Code Header)
        let columns = [];
        try {
            const registryPath = path.join(__dirname, '..', 'System', 'scripts_registry.json');
            if (fs.existsSync(registryPath)) {
                const registry = JSON.parse(fs.readFileSync(registryPath, 'utf8'));
                const entry = registry.find(r => r.filename === scriptName || r.name === scriptName);
                if (entry) {
                    columns = entry.expected_columns || (entry.columns ? entry.columns.map(c => c.name || c.header) : []);
                }
            }

            // FALLBACK 0: Read from Code Header (Truth Source)
            if (columns.length === 0) {
                try {
                    const content = fs.readFileSync(scriptPath, 'utf8');
                    const headerMatch = content.match(/#\s*EXPECTED_INPUT_COLUMNS:\s*([^\n]+)/);
                    if (headerMatch && headerMatch[1]) {
                        columns = headerMatch[1].split(',').map(c => c.trim()).filter(c => c);
                    }
                } catch (e) {
                    console.error("[Execute] Failed to parse columns from code header:", e);
                }
            }
        } catch (e) {
            console.warn(`[Execute] Failed to load columns for script: ${e.message}`);
        }

        // Prepare Arguments
        // Fix for ENAMETOOLONG: Write rows to temp file
        const timestamp = Date.now();
        const dataFileName = `run_data_${timestamp}_${Math.random().toString(36).substring(7)}.json`;
        const dataFilePath = path.join(__dirname, '..', 'temp_data', dataFileName);
        const tempDataDir = path.dirname(dataFilePath);
        try {
            if (!fs.existsSync(tempDataDir)) fs.mkdirSync(tempDataDir, { recursive: true });
            fs.writeFileSync(dataFilePath, JSON.stringify(rows));
        } catch (fileErr) {
            console.error('[Execute] Failed to write data file:', fileErr);
            return res.status(500).json({ error: 'Failed to prepare execution data' });
        }

        const args = [
            bridgePath,
            "--script", scriptPath,
            "--data-file", dataFilePath,
            "--token", token,
            "--env", JSON.stringify(envConfig || {}),
            "--columns", JSON.stringify(columns)
        ];

        // Only add debug flag if explicitly requested (e.g. from Test Run or strict debug mode)
        // We do NOT want this on by default for Production runs just because attributes are allowed.
        if (req.body.debug === true) {
            args.push("--debug");
        }

        console.log(`Executing Python Script: ${scriptName}`);
        console.log(`[Execute] Env Config:`, JSON.stringify(envConfig));

        const runner = spawn('python', ['-u', ...args], {
            env: {
                ...process.env,
                PYTHONIOENCODING: 'utf-8',
                // Add components folder to PYTHONPATH so scripts can import from it
                PYTHONPATH: process.env.PYTHONPATH
                    ? process.env.PYTHONPATH + path.delimiter + path.join(__dirname, '..')
                    : path.join(__dirname, '..'),
                GOOGLE_API_KEY: GOOGLE_API_KEY
            }
        });

        let stdoutData = '';
        let stderrData = '';

        runner.stdout.on('data', (data) => {
            const chunk = data.toString();
            stdoutData += chunk;
            process.stdout.write(chunk); // Pipe to server console
        });

        runner.stderr.on('data', (data) => {
            stderrData += data.toString();
        });

        runner.on('close', (code) => {
            // Cleanup Data File
            try { if (fs.existsSync(dataFilePath)) fs.unlinkSync(dataFilePath); } catch (e) { }

            if (code !== 0) {
                console.error(`Python Script Failed (${code}):`, stderrData);
                // Try to see if there is an error message in stdout as well
                console.error(`Python Script Output (stdout):`, stdoutData);

                return res.status(500).json({
                    error: 'Script execution failed',
                    details: stderrData + "\n---\n" + stdoutData
                });
            }

            try {
                // Parse distribution from bridge
                // Bridge prints JSON to stdout. User script might have printed logs before it.
                // We look for the last line or substring that looks like JSON.
                // The bridge prints: print(json.dumps({"status": "success", ...}))
                // So we look for the last "{" and parse from there.

                const raw = stdoutData.trim();
                // Robust Delimiter-based parsing
                const delimiter = '---JSON_START---';
                const parts = raw.split(delimiter);

                let jsonStr;
                if (parts.length < 2) {
                    // Fallback for older scripts or crash before delimiter
                    throw new Error('No JSON start delimiter found in output');
                } else {
                    jsonStr = parts[parts.length - 1].trim();
                }

                const result = JSON.parse(jsonStr);

                if (result.status === 'error') {
                    return res.status(500).json({ error: result.message, trace: result.traceback });
                }

                res.json(result.data);

            } catch (e) {
                console.error('Failed to parse Python output:', e);
                console.error('Raw Output:', stdoutData);
                // DEBUG: Show what we failed to parse
                const extractionDebug = (typeof jsonStr !== 'undefined') ? `\n[Extracted]: ${jsonStr}` : '\n[Extraction Failed]';
                res.status(500).json({
                    error: 'Invalid output from script',
                    details: `Parse Error: ${e.message}\n${extractionDebug}\n\n[Full Output]:\n${stdoutData}`
                });
            } finally {
                // Cleanup Temporary Test Scripts
                if (scriptName.startsWith('TEST_')) {
                    try {
                        if (fs.existsSync(scriptPath)) fs.unlinkSync(scriptPath);
                    } catch (cleanupErr) {
                        console.error('Warning: Failed to cleanup temp script:', cleanupErr.message);
                    }
                }
            }
        });
    });

    // Configure Multer for Script Uploads
    const upload = multer({
        storage: multer.diskStorage({
            destination: (req, file, cb) => {
                // Main Upload (Runnable Script) goes to Converted Scripts
                // relative to this file
                const dir = path.join(__dirname, '..', 'Converted Scripts');
                if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
                cb(null, dir);
            },
            filename: (req, file, cb) => {
                cb(null, file.originalname);
            }
        })
    });

    // POST Generate Token for User Aggregate
    app.post('/api/user-aggregate/token', async (req, res) => {
        const { environment, tenant, username, password } = req.body;

        if (!environment || !tenant || !username || !password) {
            return res.status(400).json({ error: 'All fields are required' });
        }

        // Determine token base URL based on environment
        const { ssoPrefix, ssoSuffix } = getEnvUrls(environment);
        const tokenBase = ssoPrefix;
        const tokenUrl = `${tokenBase}${tenant.toLowerCase()}${ssoSuffix}`;

        console.log(`[User Aggregate] Token URL: ${tokenUrl}`);

        // Prepare form data
        const formData = new URLSearchParams();
        formData.append('grant_type', 'password');
        formData.append('username', username);
        formData.append('password', password);
        formData.append('client_id', 'resource_server');
        formData.append('client_secret', 'resource_server');
        formData.append('scope', 'openid');

        try {
            const urlObj = new URL(tokenUrl);
            const postData = formData.toString();

            const options = {
                hostname: urlObj.hostname,
                port: 443,
                path: urlObj.pathname,
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Content-Length': Buffer.byteLength(postData)
                }
            };

            const tokenReq = https.request(options, (tokenRes) => {
                let data = '';

                tokenRes.on('data', (chunk) => {
                    data += chunk;
                });

                tokenRes.on('end', () => {
                    try {
                        const jsonData = JSON.parse(data);

                        if (tokenRes.statusCode >= 200 && tokenRes.statusCode < 300) {
                            res.json(jsonData);
                        } else {
                            console.error('[User Aggregate] Token Error:', tokenRes.statusCode, data);
                            res.status(tokenRes.statusCode).json({
                                error: jsonData.error_description || jsonData.error || 'Authentication failed'
                            });
                        }
                    } catch (e) {
                        console.error('[User Aggregate] Parse Error:', e);
                        res.status(500).json({ error: 'Failed to parse token response' });
                    }
                });
            });

            tokenReq.on('error', (e) => {
                console.error('[User Aggregate] Request Error:', e);
                res.status(500).json({ error: 'Token request failed: ' + e.message });
            });

            tokenReq.write(postData);
            tokenReq.end();

        } catch (err) {
            console.error('[User Aggregate] Error:', err);
            res.status(500).json({ error: 'Internal error generating token' });
        }
    });

    // 3. Upload Script
    app.post('/api/scripts/upload', upload.single('script'), (req, res) => {
        try {
            const scriptFile = req.file;
            const configJson = req.body.config;

            if (!scriptFile || !configJson) {
                return res.status(400).json({ error: 'Missing script file or config JSON' });
            }

            // 1. Validate Script (Multer saved it to Converted Scripts)
            if (!scriptFile.originalname.endsWith('.py')) {
                return res.status(400).json({ error: 'Script must be a .py file' });
            }

            // 2. [DEPRECATED] Save Config JSON to 'Script Configs'
            // Individual config files are removed in favor of scripts_registry.json
            // We skip saving individual JSON files now.

            // 3. Save Original Content (if provided) to 'Original Scripts'
            // This preserves the raw user script before auto-conversion
            if (req.body.originalContent) {
                const originalDir = path.join(__dirname, '..', 'Original Scripts');
                if (!fs.existsSync(originalDir)) fs.mkdirSync(originalDir, { recursive: true });

                const originalScriptPath = path.join(originalDir, scriptFile.originalname.replace('.py', '_original.py'));
                fs.writeFileSync(originalScriptPath, req.body.originalContent, 'utf8');
            }

            console.log(`Uploaded Script: ${scriptFile.originalname}`);
            res.json({ success: true, message: 'Script registered successfully' });

        } catch (e) {
            console.error('Upload Error:', e);
            res.status(500).json({ error: 'Internal server error during upload' });
        }
    });
    // --- Script Onboarding Endpoints ---


    // --- Script Workflow Endpoints ---

    // Generate Script Template
    app.post('/api/scripts/generate', (req, res) => {
        const { description, existing_code, scriptName, inputColumns, isMultithreaded, outputConfig, allowAdditionalAttributes, enableGeofencing } = req.body;

        console.log('[DEBUG GENERATE] Incoming Request Body:', JSON.stringify({
            scriptName,
            isMultithreaded,
            allowAdditionalAttributes,
            enableGeofencing,
            outputConfigKeys: Object.keys(outputConfig || {})
        }));

        if (!description) return res.status(400).json({ error: 'Missing description' });

        const generatorPath = path.join(__dirname, '..', 'Manager', 'script_generator.py');
        const pythonProcess = spawn('python', [generatorPath], {
            env: { ...process.env, PYTHONIOENCODING: 'utf-8', GOOGLE_API_KEY: GOOGLE_API_KEY }
        });

        let stdoutData = '';
        pythonProcess.stdout.on('data', d => stdoutData += d.toString());
        // Pass everything needed for update logic
        pythonProcess.stdin.write(JSON.stringify({
            description,
            existing_code,
            scriptName,
            inputColumns,
            isMultithreaded,
            outputConfig,
            allowAdditionalAttributes: allowAdditionalAttributes || false,
            enableGeofencing: enableGeofencing || false
        }));
        pythonProcess.stdin.end();

        pythonProcess.on('close', code => {
            if (code !== 0) return res.status(500).json({ error: 'Generator failed' });
            try {
                const parts = stdoutData.split('---JSON_START---');
                const result = JSON.parse(parts[parts.length - 1].trim());
                res.json(result);
            } catch (e) {
                res.status(500).json({ error: 'Parse error', details: stdoutData });
            }
        });
    });

    // Save Draft


    // Publish (Import)
    app.post('/api/scripts/publish', (req, res) => {
        const { filename, comments } = req.body;
        if (!filename) return res.status(400).json({ error: 'Missing filename' });

        try {
            const registryPath = path.join(__dirname, '..', 'System', 'scripts_registry.json');
            let registry = JSON.parse(fs.readFileSync(registryPath, 'utf8'));

            const entry = registry.find(r => r.filename === filename);
            if (!entry) return res.status(404).json({ error: 'Script not found' });

            entry.status = "active";
            entry.comments = comments || "";

            fs.writeFileSync(registryPath, JSON.stringify(registry, null, 2));
            res.json({ success: true });
        } catch (e) {
            res.status(500).json({ error: e.message });
        }
    });

    // Update Metadata (Team Assignment / Reusable)
    app.post('/api/scripts/update-meta', (req, res) => {
        const { filename, team, isReusable, description } = req.body;

        if (!filename) return res.status(400).json({ error: 'Missing filename' });
        // At least one field to update
        if (team === undefined && isReusable === undefined && description === undefined) {
            return res.status(400).json({ error: 'Nothing to update' });
        }

        try {
            const registryPath = path.join(__dirname, '..', 'System', 'scripts_registry.json');
            let registry = JSON.parse(fs.readFileSync(registryPath, 'utf8'));

            const entry = registry.find(r => r.filename === filename);
            if (!entry) return res.status(404).json({ error: 'Script not found' });

            if (team !== undefined) entry.team = team;
            if (isReusable !== undefined) entry.isReusable = isReusable;
            if (description !== undefined) entry.description = description;

            fs.writeFileSync(registryPath, JSON.stringify(registry, null, 2));

            // [DEPRECATED] Update individual config file
            // Configs are now consolidated in scripts_registry.json only.

            res.json({ success: true });
        } catch (e) {
            res.status(500).json({ error: e.message });
        }
    });

    // Delete (Discard)
    // Delete (Discard)
    app.post('/api/scripts/delete', (req, res) => {
        const { filename } = req.body;
        if (!filename) return res.status(400).json({ error: 'Missing filename' });

        try {
            const cleanName = filename.replace('.py', '');
            const pyName = `${cleanName}.py`;
            const jsonName = `${cleanName}.json`;
            const metaName = `${cleanName}.py.meta.json`;

            // Paths
            const draftsDir = path.join(__dirname, '..', 'Draft Scripts');
            const scriptsDir = path.join(__dirname, '..', 'Converted Scripts');
            // const originalDir = path.join(__dirname, '..', 'Original Scripts'); // DEPRECATED
            const registryPath = path.join(__dirname, '..', 'System', 'scripts_registry.json');

            // 1. Try Delete from Drafts (Always check, even if Active, per usage)
            if (fs.existsSync(path.join(draftsDir, pyName))) fs.unlinkSync(path.join(draftsDir, pyName));
            if (fs.existsSync(path.join(draftsDir, metaName))) fs.unlinkSync(path.join(draftsDir, metaName));

            // 2. [DEPRECATED] Delete Active Files (Individual Configs)
            if (fs.existsSync(path.join(scriptsDir, pyName))) fs.unlinkSync(path.join(scriptsDir, pyName));

            // 3. Update Registry
            if (fs.existsSync(registryPath)) {
                let registry = JSON.parse(fs.readFileSync(registryPath, 'utf8'));
                const originalLength = registry.length;
                registry = registry.filter(r => r.filename !== filename && r.name !== filename);

                if (registry.length !== originalLength) {
                    fs.writeFileSync(registryPath, JSON.stringify(registry, null, 2));
                }
            }

            res.json({ success: true, message: 'Script deleted successfully' });
        } catch (e) {
            console.error("Delete failed:", e);
            res.status(500).json({ error: e.message });
        }
    });

    // Save Feedback (For AI Agent)
    app.post('/api/scripts/save-feedback', (req, res) => {
        try {
            const feedbackPath = path.join(__dirname, '..', 'agent_feedback.json');
            fs.writeFileSync(feedbackPath, JSON.stringify(req.body, null, 2));
            res.json({ success: true });
        } catch (e) {
            res.status(500).json({ error: e.message });
        }
    });

    // 4. Analyze Script
    app.post('/api/scripts/analyze', (req, res) => {
        const { code } = req.body;
        if (!code) return res.status(400).json({ error: 'Missing code' });

        const analyzerPath = path.join(__dirname, '..', 'Manager', 'script_analyzer.py');

        // Spawn Python Analyzer
        const pythonProcess = spawn('python', [analyzerPath], {
            env: { ...process.env, PYTHONIOENCODING: 'utf-8', GOOGLE_API_KEY: GOOGLE_API_KEY }
        });

        let stdoutData = '';
        let stderrData = '';

        pythonProcess.stdout.on('data', (data) => stdoutData += data.toString());
        pythonProcess.stderr.on('data', (data) => stderrData += data.toString());

        // Write code to stdin
        pythonProcess.stdin.write(code);
        pythonProcess.stdin.end();

        pythonProcess.on('close', (code) => {
            if (code !== 0) {
                return res.status(500).json({ error: 'Analysis failed', details: stderrData });
            }
            try {
                const delimiter = '---JSON_START---';
                const parts = stdoutData.split(delimiter);
                if (parts.length < 2) throw new Error('No JSON output from analyzer');

                const result = JSON.parse(parts[parts.length - 1].trim());
                if (result.status === 'error') return res.status(400).json(result);

                res.json(result.data);
            } catch (e) {
                res.status(500).json({ error: 'Failed to parse analyzer output', details: stdoutData });
            }
        });
    });

    // 5. Test Run (Temporary)
    app.post('/api/scripts/test-run', async (req, res) => {
        console.log('[Test Run] Received Request.');
        const { code, rows, token, envConfig, columns } = req.body;
        if (!code || !rows || !token) return res.status(400).json({ error: 'Missing parameters' });

        // Inject apiBaseUrl from DB if environment is present
        if (envConfig && envConfig.environment) {
            console.log(`[Test Run] Resolving URL for env: ${envConfig.environment}`);
            const { apiBaseUrl } = getEnvUrls(envConfig.environment);
            console.log(`[Test Run] Found apiBaseUrl: ${apiBaseUrl}`);

            if (apiBaseUrl) {
                envConfig.apiBaseUrl = apiBaseUrl;
            }

        } else {
            console.log('[Test Run] No environment in envConfig');
        }

        // Always inject master_data_config from DB
        try {
            const dbRef = readDb();
            envConfig.master_data_config = dbRef.master_data_config || {};
            console.log(`[Test Run] Injected master_data_config. Keys: ${Object.keys(envConfig.master_data_config).join(', ')}`);
        } catch (e) {
            console.error('[Test Run] Failed to read/inject master_data_config:', e);
        }

        // Create Temp File
        const tempName = `TEST_${Date.now()}.py`;
        // Save in Converted Scripts temporarily so the runner can find it
        const tempPath = path.join(__dirname, '..', 'Converted Scripts', tempName);

        // 1. Clean/Convert the script using script_converter.py
        const converterPath = path.join(__dirname, '..', 'Manager', 'script_converter.py');

        const runConversion = () => {
            return new Promise((resolve, reject) => {
                const pyProc = spawn('python', [converterPath], {
                    env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
                });
                let result = '';
                let err = '';

                pyProc.stdout.on('data', d => result += d.toString());
                pyProc.stderr.on('data', d => err += d.toString());

                pyProc.on('close', (code) => {
                    if (code !== 0) reject(err || 'Conversion failed');
                    else resolve(result);
                });

                pyProc.stdin.write(code);
                pyProc.stdin.end();
            });
        };

        let cleanedCode = '';
        try {
            console.log('[Test Run] Starting conversion...');
            cleanedCode = await runConversion();
            console.log('[Test Run] Conversion success. Length:', cleanedCode.length);
            fs.writeFileSync(tempPath, cleanedCode, 'utf8');
        } catch (e) {
            console.error('[Test Run] Conversion Failed:', e);
            // Return validation error to user instead of ignoring it
            return res.status(500).json({
                error: 'Script Conversion Failed',
                details: e.toString(),
                hint: 'Please check your script syntax or import paths.'
            });
        }

        const bridgePath = path.join(__dirname, '..', 'Manager', 'runner_bridge.py');
        const args = [
            bridgePath,
            "--script", tempPath,
            "--data", JSON.stringify(rows),
            "--token", token,
            "--env", JSON.stringify(envConfig || {}),
            "--columns", JSON.stringify(columns || []),
            "--debug" // ENABLE DEBUG LOGGING FOR TEST RUN
        ];

        console.log('[Test Run] Spawning Python process with args:', args.map((a, i) =>
            i === 0 ? a : (args[i - 1] === '--token' ? '[REDACTED]' : (args[i - 1] === '--data' ? '[DATA]' : a))
        ).join(' '));

        const pythonProcess = spawn('python', args, {
            env: {
                ...process.env,
                PYTHONIOENCODING: 'utf-8',
                PYTHONPATH: process.env.PYTHONPATH
                    ? process.env.PYTHONPATH + path.delimiter + path.join(__dirname, '..')
                    : path.join(__dirname, '..'),
                GOOGLE_API_KEY: GOOGLE_API_KEY
            }
        });

        // Set a timeout to prevent indefinite hanging (90 seconds)
        const TIMEOUT_MS = 90000;
        let processCompleted = false;
        let timeoutHandle = setTimeout(() => {
            if (!processCompleted) {
                console.error('[Test Run] TIMEOUT: Process exceeded 90 seconds. Killing process.');
                pythonProcess.kill('SIGTERM');

                // Give it 2 seconds to cleanup, then force kill
                setTimeout(() => {
                    if (!processCompleted) {
                        console.error('[Test Run] Force killing process.');
                        pythonProcess.kill('SIGKILL');
                    }
                }, 2000);

                // Cleanup temp file
                try { if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath); } catch (e) { }

                return res.status(500).json({
                    error: 'Test run timeout',
                    details: 'The script execution exceeded 90 seconds and was terminated. This may indicate an infinite loop, deadlock, or network issue.',
                    logs: stdoutData,
                    stderr: stderrData,
                    convertedCode: cleanedCode
                });
            }
        }, TIMEOUT_MS);

        let stdoutData = '';
        let stderrData = '';

        pythonProcess.stdout.on('data', d => {
            const chunk = d.toString();
            stdoutData += chunk;
            // Log stdout in real-time for debugging
            if (chunk.includes('DEBUG:') || chunk.includes('ERROR') || chunk.includes('RUNNER STARTING')) {
                console.log('[Test Run] Python stdout:', chunk.substring(0, 200));
            }
        });

        pythonProcess.stderr.on('data', d => {
            const chunk = d.toString();
            stderrData += chunk;
            // Log stderr immediately for debugging
            console.error('[Test Run] Python stderr:', chunk.substring(0, 500));
        });

        pythonProcess.on('error', (err) => {
            processCompleted = true;
            clearTimeout(timeoutHandle);
            console.error('[Test Run] Process error:', err);

            // Cleanup
            try { if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath); } catch (e) { }

            return res.status(500).json({
                error: 'Failed to spawn Python process',
                details: err.message,
                hint: 'Make sure Python is installed and accessible in PATH'
            });
        });

        pythonProcess.on('close', (code) => {
            processCompleted = true;
            clearTimeout(timeoutHandle);

            console.log(`[Test Run] Process closed with code: ${code}`);

            // Cleanup
            try { if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath); } catch (e) { }

            if (code !== 0 && code !== null) {
                // PARTIAL SUCCESS CHECK:
                // If the script crashed/failed but still managed to print [OUTPUT_DATA_DUMP], 
                // we should allow the user to download the partial result.
                if (stdoutData.includes('[OUTPUT_DATA_DUMP]')) {
                    console.log('[Test Run] Script failed but Output Dump detected. Returning Partial Success.');
                    // Proceed to parsing logic below instead of returning 500
                } else {
                    const truncatedStderr = stderrData.length > 5000 ? stderrData.substring(0, 5000) + '... [TRUNCATED]' : stderrData;
                    const truncatedStdout = stdoutData.length > 5000 ? stdoutData.substring(0, 5000) + '... [TRUNCATED]' : stdoutData;
                    console.error('[Test Run] Execution ERROR. Stderr:', truncatedStderr);

                    return res.status(500).json({
                        error: 'Execution failed',
                        details: truncatedStderr || 'Process exited with error code',
                        logs: truncatedStdout,
                        convertedCode: cleanedCode
                    });
                }
            }

            try {
                const delimiter = '---JSON_START---';
                const parts = stdoutData.split(delimiter);
                const logs = parts[0];
                const jsonStr = parts.length > 1 ? parts[parts.length - 1].trim() : "{}";

                let resultData = {};
                try { resultData = JSON.parse(jsonStr); } catch (e) {
                    console.error('[Test Run] Failed to parse JSON result:', e.message);
                }

                res.json({
                    logs: logs,
                    result: resultData,
                    rawOutput: stdoutData,
                    convertedCode: cleanedCode // DEBUG: Show what was actually run
                });
            } catch (e) {
                console.error('[Test Run] Output parsing error:', e);
                res.status(500).json({ error: 'Output parsing failed', raw: stdoutData });
            }
        });
    });

    // RENAME SCRIPT
    app.post('/api/scripts/rename', async (req, res) => {
        try {
            const { oldName, newName } = req.body; // Expects "OldName.py" or just "OldName"? Let's handle both.
            if (!oldName || !newName) return res.status(400).json({ error: 'Missing oldName or newName' });

            // Normalize names (remove .py if present to be safe, then append)
            const cleanOld = oldName.replace(/\.py$/, '');
            const cleanNew = newName.replace(/\.py$/, '').replace(/[^a-zA-Z0-9_-]/g, '_'); // Sanitize new name

            if (cleanNew.length === 0) return res.status(400).json({ error: 'Invalid new name' });

            const oldPyName = `${cleanOld}.py`;
            const newPyName = `${cleanNew}.py`;
            const oldJsonName = `${cleanOld}.json`; // Config
            const newJsonName = `${cleanNew}.json`;
            const oldMetaName = `${cleanOld}.py.meta.json`; // Draft Meta
            const newMetaName = `${cleanNew}.py.meta.json`;

            const draftsDir = path.join(__dirname, '..', 'Draft Scripts');
            const scriptsDir = path.join(__dirname, '..', 'Converted Scripts');
            const registryPath = path.join(__dirname, '..', 'System', 'scripts_registry.json');
            // const originalDir = path.join(__dirname, '..', 'Original Scripts'); // DEPRECATED

            let renamedAny = false;

            // 1. Rename Drafts
            if (fs.existsSync(path.join(draftsDir, oldPyName))) {
                fs.renameSync(path.join(draftsDir, oldPyName), path.join(draftsDir, newPyName));
                renamedAny = true;
            }
            if (fs.existsSync(path.join(draftsDir, oldMetaName))) {
                // Read meta, update name/filename inside, then write to new path
                try {
                    const meta = JSON.parse(fs.readFileSync(path.join(draftsDir, oldMetaName), 'utf8'));
                    meta.name = newPyName; // Update internal name
                    meta.filename = newPyName;
                    fs.writeFileSync(path.join(draftsDir, newMetaName), JSON.stringify(meta, null, 2), 'utf8');
                    fs.unlinkSync(path.join(draftsDir, oldMetaName)); // Delete old
                } catch (e) {
                    // Fallback if semantic update fails: just rename
                    fs.renameSync(path.join(draftsDir, oldMetaName), path.join(draftsDir, newMetaName));
                }
                renamedAny = true;
            }

            // 2. [DEPRECATED] Rename Registered Configs
            // Individual config files are removed. Renaming is skipped.

            // 3. Rename Converted Script
            if (fs.existsSync(path.join(scriptsDir, oldPyName))) {
                fs.renameSync(path.join(scriptsDir, oldPyName), path.join(scriptsDir, newPyName));
                renamedAny = true;
            }

            // 4. Rename Original Script (if exists) -> DEPRECATED
            // if (fs.existsSync(path.join(originalDir, oldPyName))) {
            //     fs.renameSync(path.join(originalDir, oldPyName), path.join(originalDir, newPyName));
            // }

            // 5. Update Registry
            if (fs.existsSync(registryPath)) {
                try {
                    let registry = JSON.parse(fs.readFileSync(registryPath, 'utf8'));
                    const entryIndex = registry.findIndex(r => r.name === oldPyName || r.filename === oldPyName);
                    if (entryIndex >= 0) {
                        registry[entryIndex].name = newPyName;
                        registry[entryIndex].filename = newPyName;
                        fs.writeFileSync(registryPath, JSON.stringify(registry, null, 2), 'utf8');
                        renamedAny = true;
                    }
                } catch (e) { console.error("Registry update failed during rename", e); }
            }

            if (!renamedAny) {
                return res.status(404).json({ error: 'Script not found (Draft or Active)' });
            }

            res.json({ success: true, newName: newPyName });

        } catch (e) {
            console.error("Rename failed:", e);
            res.status(500).json({ error: 'Rename failed: ' + e.message });
        }
    });

    // REGISTER SCRIPT
    app.post('/api/scripts/register', async (req, res) => {
        try {
            const { code, name, team, description, inputColumns, generationPrompt, isMultithreaded, groupByColumn, batchSize } = req.body;

            if (!code || !name) return res.status(400).json({ error: 'Missing code or name' });

            // 1. Convert Code (Final pass for storage)
            const converterPath = path.join(__dirname, '..', 'Manager', 'script_converter.py');
            const runConversion = () => {
                return new Promise((resolve, reject) => {
                    const args = [converterPath];
                    if (isMultithreaded === false) {
                        args.push('--no-threading');
                    }

                    const pyProc = spawn('python', args, {
                        env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
                    });
                    let result = '';
                    let err = '';
                    pyProc.stdout.on('data', d => result += d.toString());
                    pyProc.stderr.on('data', d => err += d.toString());
                    pyProc.on('close', (c) => {
                        if (c !== 0) reject(err || 'Conversion failed');
                        else resolve(result);
                    });
                    pyProc.stdin.write(code);
                    pyProc.stdin.end();
                });
            };

            let cleanedCode;
            try {
                cleanedCode = await runConversion();
            } catch (e) {
                return res.status(500).json({ error: 'Conversion failed during registration', details: e.toString() });
            }

            // 2. Generate Filenames
            const safeName = name.replace(/[^a-zA-Z0-9_-]/g, '_');
            const pyFilename = `${safeName}.py`;

            const scriptsDir = path.join(__dirname, '..', 'Converted Scripts');
            const draftsDir = path.join(__dirname, '..', 'Draft Scripts');
            // const originalDir = path.join(__dirname, '..', 'Original Scripts'); // DEPRECATED

            // Ensure dirs exist
            if (!fs.existsSync(scriptsDir)) fs.mkdirSync(scriptsDir, { recursive: true });
            if (!fs.existsSync(draftsDir)) fs.mkdirSync(draftsDir, { recursive: true });

            // 3. Save Python File
            fs.writeFileSync(path.join(scriptsDir, pyFilename), cleanedCode, 'utf8');

            // 4. Create & Save JSON Config

            // SERVER-SIDE EXTRACTION: Ensure Config is synced from Code
            // This prevents "Data Loss" if the UI sent empty values.
            let finalGroupBy = groupByColumn;
            let finalBatchSize = batchSize || 10;
            let finalIsMultithreaded = isMultithreaded;

            try {
                const groupMatch = code.match(/#\s*CONFIG:\s*groupByColumn\s*=\s*["']([^"']+)["']/);
                if (groupMatch && groupMatch[1]) finalGroupBy = groupMatch[1];

                const batchMatch = code.match(/#\s*CONFIG:\s*batchSize\s*=\s*(\d+)/);
                if (batchMatch && batchMatch[1]) finalBatchSize = parseInt(batchMatch[1]);

                const mtMatch = code.match(/#\s*CONFIG:\s*isMultithreaded\s*=\s*(True|False|true|false)/i);
                if (mtMatch && mtMatch[1]) finalIsMultithreaded = (mtMatch[1].toLowerCase() === 'true');
            } catch (e) { console.error("Error parsing code config during register:", e); }

            // Extract Boolean Configs from Code (Truth Source)
            let finalEnableGeofencing = req.body.enableGeofencing || false;
            let finalAllowAttributes = req.body.allowAdditionalAttributes || false;
            try {
                const geoMatch = code.match(/#\s*CONFIG:\s*enableGeofencing\s*=\s*(True|False|true|false)/i);
                if (geoMatch && geoMatch[1]) finalEnableGeofencing = (geoMatch[1].toLowerCase() === 'true');

                const attrMatch = code.match(/#\s*CONFIG:\s*allowAdditionalAttributes\s*=\s*(True|False|true|false)/i);
                if (attrMatch && attrMatch[1]) finalAllowAttributes = (attrMatch[1].toLowerCase() === 'true');
            } catch (e) { console.error("Error parsing boolean configs:", e); }

            const config = {
                name: `${name}.py`,
                filename: pyFilename,
                team: team || "Unassigned",
                description: description || "Custom User Script",
                expected_columns: (inputColumns || []).map(c => (typeof c === 'object' && c.name) ? c.name : c),
                columns: inputColumns,
                requiresLogin: true,
                isMultithreaded: finalIsMultithreaded,
                batchSize: finalBatchSize,
                groupByColumn: finalGroupBy,
                enableGeofencing: finalEnableGeofencing,
                allowAdditionalAttributes: finalAllowAttributes,
                additionalAttributes: req.body.additionalAttributes || [],
                outputConfig: req.body.outputConfig || {}
            };

            // 4. [DEPRECATED] Save JSON Config
            // Configs are now consolidated in scripts_registry.json.
            // We skip saving individual JSON files.

            // 4b. Save Sidecar Meta JSON - DISABLED (Single Flow Architecture)
            // User requested NO redundant files in Converted Scripts.
            // Meta info is saved in Registry (generation_prompt) and Code Headers (columns/config).
            /*
            const metaFilename = `${pyFilename}.meta.json`;
            const metaPath = path.join(scriptsDir, metaFilename); 

            // Construct full meta object (superset of config)
            const fullMeta = {
                ...config,
                generationPrompt: generationPrompt,
                draftSource: name // trace back
            };
            fs.writeFileSync(metaPath, JSON.stringify(fullMeta, null, 4), 'utf8');
            */


            // 5. Update Registry
            const registryPath = path.join(__dirname, '..', 'System', 'scripts_registry.json');
            let registry = [];
            if (fs.existsSync(registryPath)) {
                try {
                    registry = JSON.parse(fs.readFileSync(registryPath, 'utf8'));
                } catch (e) { console.error("Registry read error", e); }
            }

            // Upsert Logic: Find existing to preserve other fields if needed, or merge new
            const existingIndex = registry.findIndex(r => r.name === config.name);

            if (existingIndex >= 0) {
                registry[existingIndex] = {
                    ...registry[existingIndex],
                    ...config,
                    generation_prompt: generationPrompt // Save/Update the prompt
                };
            } else {
                registry.push({
                    ...config,
                    generation_prompt: generationPrompt // Save the prompt
                });
            }

            fs.writeFileSync(registryPath, JSON.stringify(registry, null, 2), 'utf8');

            res.json({ success: true, filename: pyFilename });

            // 6. Cleanup Draft if exists
            try {
                const draftPath = path.join(draftsDir, pyFilename);
                if (fs.existsSync(draftPath)) {
                    fs.unlinkSync(draftPath);
                    console.log(`Cleaned up draft: ${draftPath}`);
                }
                // Also clean up draft meta
                const draftMetaPath = path.join(draftsDir, pyFilename + '.meta.json');
                if (fs.existsSync(draftMetaPath)) {
                    fs.unlinkSync(draftMetaPath);
                }
            } catch (e) { }

        } catch (e) {
            console.error("Registration Error", e);
            res.status(500).json({ error: e.message });
        }
    });

    // 5. List Generated Scripts
    app.get('/api/scripts/list', (req, res) => {
        const scriptsDir = path.join(__dirname, '..', 'Converted Scripts');

        if (!fs.existsSync(scriptsDir)) {
            return res.json([]);
        }

        try {
            const SYSTEM_FILES = [
                'thread_utils.py',
                'attribute_utils.py',
                'algorithm_utils.py',
                'DraftTest.py',
                'TestScript.py'
            ];

            const files = fs.readdirSync(scriptsDir)
                .filter(file => {
                    if (!file.endsWith('.py')) return false;
                    if (file.startsWith('__init__')) return false;
                    if (file.startsWith('TEST_')) return false;
                    if (SYSTEM_FILES.includes(file)) return false;
                    return true;
                })
                .map(file => ({
                    name: file,
                    path: path.join(scriptsDir, file),
                    mtime: fs.statSync(path.join(scriptsDir, file)).mtime
                }))
                .sort((a, b) => b.mtime - a.mtime); // Sort by newest first

            res.json(files);
        } catch (e) {
            console.error('Error listing scripts:', e);
            res.status(500).json({ error: 'Failed to list scripts' });
        }
    });

    // 6. Get Script Content
    app.get('/api/scripts/content', (req, res) => {
        const { filename } = req.query;
        if (!filename) return res.status(400).json({ error: 'Filename required' });

        const scriptPath = path.join(__dirname, '..', 'Converted Scripts', filename);

        if (!fs.existsSync(scriptPath)) {
            return res.status(404).json({ error: 'Script not found' });
        }

        try {
            const content = fs.readFileSync(scriptPath, 'utf8');

            // Strategy:
            // 1. Check for Sidecar .meta.json (Highest Priority for Deployed Scripts)
            // 2. Check Registry
            // 3. Draft Healer (Fallback)

            let meta = {};
            let prompt = "";

            // 1. Sidecar Meta
            const sidecarPath = path.join(__dirname, '..', 'Converted Scripts', filename + '.meta.json');
            if (fs.existsSync(sidecarPath)) {
                try {
                    const sidecar = JSON.parse(fs.readFileSync(sidecarPath, 'utf8'));
                    meta = sidecar;
                    prompt = sidecar.generationPrompt || "";
                    // console.log(`[Content] Loaded meta from sidecar for ${filename}`);
                } catch (e) { console.error("Sidecar read failed", e); }
            }

            // 2. Registry (If sidecar missing or incomplete?)
            if (!meta.name) {
                try {
                    const registryPath = path.join(__dirname, '..', 'System', 'scripts_registry.json');
                    if (fs.existsSync(registryPath)) {
                        const reg = JSON.parse(fs.readFileSync(registryPath, 'utf8'));
                        const item = reg.find(r => r.filename === filename);
                        if (item) {
                            prompt = item.generation_prompt;
                            meta = item; // Send full item as meta
                        }
                    }
                } catch (e) { console.error("Registry lookup failed:", e); }
            }

            // 3. Draft Healer (Fallback)
            // ... (Keep existing healer logic if still needed, but sidecar should cover it)
            if (!meta.groupByColumn || !meta.batchSize) {
                try {
                    const draftsDir = path.join(__dirname, '..', 'Draft Scripts');
                    const draftMetaPath = path.join(draftsDir, filename + '.meta.json');
                    if (fs.existsSync(draftMetaPath)) {
                        const draftMeta = JSON.parse(fs.readFileSync(draftMetaPath, 'utf8'));

                        // Only backfill if missing 
                        if (!meta.groupByColumn && draftMeta.groupByColumn) meta.groupByColumn = draftMeta.groupByColumn;
                        if (!meta.batchSize && draftMeta.batchSize) meta.batchSize = draftMeta.batchSize;
                        if (meta.isMultithreaded === undefined && draftMeta.isMultithreaded !== undefined) {
                            meta.isMultithreaded = draftMeta.isMultithreaded;
                        }
                        // Also fill columns if missing!
                        if ((!meta.columns || meta.columns.length === 0) && draftMeta.inputColumns) {
                            meta.columns = draftMeta.inputColumns;
                        }
                    }
                } catch (e) { console.error("Draft Healer failed:", e); }
            }

            // OVERRIDE: Extract Config from Code Content (Truth Source)
            const groupMatch = content.match(/#\s*CONFIG:\s*groupByColumn\s*=\s*["']([^"']+)["']/);
            if (groupMatch && groupMatch[1]) meta.groupByColumn = groupMatch[1];

            const batchMatch = content.match(/#\s*CONFIG:\s*batchSize\s*=\s*(\d+)/);
            if (batchMatch && batchMatch[1]) meta.batchSize = parseInt(batchMatch[1]);

            const mtMatch = content.match(/#\s*CONFIG:\s*isMultithreaded\s*=\s*(True|False|true|false)/i);
            if (mtMatch && mtMatch[1]) meta.isMultithreaded = (mtMatch[1].toLowerCase() === 'true');

            const geoMatch = content.match(/#\s*CONFIG:\s*enableGeofencing\s*=\s*(True|False|true|false)/i);
            if (geoMatch && geoMatch[1]) meta.enableGeofencing = (geoMatch[1].toLowerCase() === 'true');

            const attrMatch = content.match(/#\s*CONFIG:\s*allowAdditionalAttributes\s*=\s*(True|False|true|false)/i);
            if (attrMatch && attrMatch[1]) meta.allowAdditionalAttributes = (attrMatch[1].toLowerCase() === 'true');

            // FALLBACK: Parse columns from Code Header (Truth Source)
            const headerMatch = content.match(/#\s*EXPECTED_INPUT_COLUMNS:\s*([^\n]+)/);
            if (headerMatch && headerMatch[1]) {
                meta.columns = headerMatch[1].split(',').map(c => c.trim()).filter(c => c);
            }
            // FALLBACK: REMOVED (User requested single flow - Code Header is Source of Truth)

            res.json({ content, generationPrompt: prompt, meta: meta });
        } catch (e) {
            res.status(500).json({ error: 'Failed to read script' });
        }
    });



    // 7. Save Feedback / Context
    app.post('/api/scripts/save-feedback', (req, res) => {
        try {
            const { scriptName, code, comments, logs, timestamp } = req.body;
            console.log("---------------------------------------------------");
            console.log(`[FEEDBACK RECEIVED] Time: ${timestamp}`);
            console.log(`Script: ${scriptName}`);
            console.log(`Comments: ${comments}`);
            console.log("---------------------------------------------------");

            // Optionally save to file for persistence check
            const feedbackPath = path.join(__dirname, '..', 'feedback.log');
            const entry = `\n[${timestamp}] Script: ${scriptName}\nComments: ${comments}\n`;
            fs.appendFileSync(feedbackPath, entry, 'utf8');

            res.json({ success: true, message: "Feedback logged successfully" });
        } catch (e) {
            console.error("Feedback Error:", e);
            res.status(500).json({ error: e.message });
        }
    });
    // 7.b Reverse Engineer Script (AI)
    app.post('/api/scripts/reverse-engineer', (req, res) => {
        const { code } = req.body;
        if (!code) return res.status(400).json({ error: 'Missing code' });

        const reverserPath = path.join(__dirname, '..', 'Manager', 'script_reverser.py');

        const pythonProcess = spawn('python', [reverserPath], {
            env: { ...process.env, PYTHONIOENCODING: 'utf-8', GOOGLE_API_KEY: GOOGLE_API_KEY }
        });

        let stdoutData = '';
        let stderrData = '';

        pythonProcess.stdout.on('data', d => stdoutData += d.toString());
        pythonProcess.stderr.on('data', d => stderrData += d.toString());

        pythonProcess.stdin.write(JSON.stringify({ code }));
        pythonProcess.stdin.end();

        pythonProcess.on('close', code => {
            if (code !== 0) {
                return res.json({ error: 'Reverser process failed', details: stderrData });
            }
            try {
                const parts = stdoutData.split('---JSON_START---');
                const result = JSON.parse(parts[parts.length - 1].trim());
                res.json(result);
            } catch (e) {
                res.json({ error: 'Parse error from reverser', details: stdoutData });
            }
        });
    });

    // 8. DRAFT ENDPOINTS
    app.post('/api/scripts/save-draft', (req, res) => {
        try {
            const { code, name, originalFilename } = req.body;
            if (!code || !name) return res.status(400).json({ error: "Missing code or name" });

            const draftsDir = path.join(__dirname, '..', 'Draft Scripts');
            // const originalDir = path.join(__dirname, '..', 'Original Scripts'); // DEPRECATED

            if (!fs.existsSync(draftsDir)) fs.mkdirSync(draftsDir, { recursive: true });
            // if (!fs.existsSync(originalDir)) fs.mkdirSync(originalDir, { recursive: true });

            const filename = (name.endsWith('.py') ? name : `${name}.py`).replace(/[^a-zA-Z0-9_-]/g, '_').replace(/_py$/, '.py');
            const draftPath = path.join(draftsDir, filename);

            // SAVE ORIGINAL (If New / Not Exists) -> DEPRECATED
            // Captures the initial state (e.g. pasted code) before draft edits
            // const originalPath = path.join(originalDir, filename.replace('.py', '_original.py'));
            // if (!fs.existsSync(originalPath)) {
            //     fs.writeFileSync(originalPath, code, 'utf8');
            //     console.log(`[Save Draft] Preserved original content for: ${filename}`);
            // }

            fs.writeFileSync(draftPath, code, 'utf8');

            // Save Metadata Sidecar
            const { description, generationPrompt, inputColumns, team, groupByColumn, isMultithreaded, batchSize, outputConfig } = req.body;

            // FIX: STRICT MODE - Do not extract from prompt. Blindly follow inputColumns.
            let finalInputColumns = inputColumns || [];
            // REMOVED HEALER LOGIC PER USER REQUEST

            const metaPath = path.join(draftsDir, filename + '.meta.json');
            const meta = {
                description: description || "",
                generationPrompt: generationPrompt || description || "", // Fallback for legacy
                inputColumns: finalInputColumns,
                team: team || "Unassigned",
                groupByColumn: groupByColumn,
                isMultithreaded: isMultithreaded,
                isMultithreaded: isMultithreaded,
                enableGeofencing: req.body.enableGeofencing || false,
                allowAdditionalAttributes: req.body.allowAdditionalAttributes || false,
                additionalAttributes: req.body.additionalAttributes || [],
                batchSize: batchSize || 10,
                outputConfig: outputConfig || {},
                mtime: Date.now()
            };
            fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2), 'utf8');



            // --- RENAME LOGIC: Cleanup Old Draft if Rename detected ---
            if (originalFilename && originalFilename !== filename) {
                try {
                    const oldPath = path.join(draftsDir, originalFilename);
                    const oldMetaPath = path.join(draftsDir, originalFilename + '.meta.json');

                    if (fs.existsSync(oldPath)) {
                        fs.unlinkSync(oldPath);
                        console.log(`[Rename] Deleted old draft: ${originalFilename}`);
                    }
                    if (fs.existsSync(oldMetaPath)) {
                        fs.unlinkSync(oldMetaPath);
                    }
                } catch (e) {
                    console.error("[Rename] Error cleaning up old draft:", e);
                }
            }

            res.json({ success: true, message: "Draft saved", filename: filename });
        } catch (e) {
            res.status(500).json({ error: e.message });
        }
    });

    app.get('/api/scripts/list-drafts', (req, res) => {
        const draftsDir = path.join(__dirname, '..', 'Draft Scripts');
        if (!fs.existsSync(draftsDir)) return res.json([]);
        const SYSTEM_FILES = ['DraftTest.py', 'TestScript.py'];

        try {
            const files = fs.readdirSync(draftsDir)
                .filter(file => file.endsWith('.py'))
                .filter(file => !SYSTEM_FILES.includes(file)) // Filter Blacklist
                .map(file => {
                    // Try load metadata
                    let meta = {};
                    const metaPath = path.join(draftsDir, file + '.meta.json');
                    if (fs.existsSync(metaPath)) {
                        try { meta = JSON.parse(fs.readFileSync(metaPath, 'utf8')); } catch (e) { }
                    }
                    return {
                        name: file,
                        path: path.join(draftsDir, file),
                        mtime: fs.statSync(path.join(draftsDir, file)).mtime,
                        ...meta // Spread metadata (team, description)
                    };
                })
                .sort((a, b) => b.mtime - a.mtime);
            res.json(files);
        } catch (e) {
            res.status(500).json({ error: "List failed" });
        }
    });

    app.get('/api/scripts/content-draft', (req, res) => {
        const { filename } = req.query;
        if (!filename) return res.status(400).json({ error: "Filename required" });
        const draftsDir = path.join(__dirname, '..', 'Draft Scripts');
        const scriptPath = path.join(draftsDir, filename);

        if (fs.existsSync(scriptPath)) {
            const content = fs.readFileSync(scriptPath, 'utf8');

            // Try load metadata
            let meta = {};

            try {
                const metaPath = path.join(draftsDir, filename + '.meta.json');
                if (fs.existsSync(metaPath)) {
                    let rawMeta = fs.readFileSync(metaPath, 'utf8');
                    // Strip BOM if present
                    if (rawMeta.charCodeAt(0) === 0xFEFF) {
                        rawMeta = rawMeta.slice(1);
                    }
                    meta = JSON.parse(rawMeta);
                }
            } catch (e) {
                console.error("Meta parse error:", e);
            }

            // OVERRIDE: Extract Config from Code Content (Truth Source)
            // Only if NOT present in metadata (Preserve User UI Choice)
            const groupMatch = content.match(/#\s*CONFIG:\s*groupByColumn\s*=\s*["']([^"']+)["']/);
            if (!meta.groupByColumn && groupMatch && groupMatch[1]) meta.groupByColumn = groupMatch[1];

            const batchMatch = content.match(/#\s*CONFIG:\s*batchSize\s*=\s*(\d+)/);
            if (!meta.batchSize && batchMatch && batchMatch[1]) meta.batchSize = parseInt(batchMatch[1]);

            const mtMatch = content.match(/#\s*CONFIG:\s*isMultithreaded\s*=\s*(True|False|true|false)/i);
            // Explicit check for undefined because false is a valid value
            if (meta.isMultithreaded === undefined && mtMatch && mtMatch[1]) {
                meta.isMultithreaded = (mtMatch[1].toLowerCase() === 'true');
            }

            res.json({
                content: content,
                generationPrompt: meta.generationPrompt || meta.description || "",
                description: meta.description || "",
                inputColumns: meta.inputColumns || [],
                meta: meta
            });
        } else {
            res.status(404).json({ error: "Draft not found" });
        }
    });

    // Startup Log
};
