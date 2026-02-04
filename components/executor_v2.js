/**
 * ScriptExecutorV2
 * A modern, modular execution engine for Data Generate scripts.
 * 
 * Features:
 * - Clean Separation of Concerns (Config, API, Response)
 * - Standardized Error Handling
 * - Dynamic Configuration Support
 * - Future-Proof for API V2 upgrades
 */
class ScriptExecutorV2 {
    constructor(config = {}) {
        this.apiBaseUrl = config.apiBaseUrl || '';
        this.debug = config.debug || false;
    }

    /**
     * Parse and sanitize the configuration for the backend.
     * Ensures all required fields (boundary, env, token) are present and correctly nested.
     */
    preparePayload(scriptName, rows, token, envConfig, meta = {}) {
        // Deep clone to avoid mutation
        const cleanConfig = JSON.parse(JSON.stringify(envConfig));

        // Ensure Boundary Object exists if coordinates are present
        if (!cleanConfig.boundary) {
            cleanConfig.boundary = {};
        }

        // Map flat UI fields to structured boundary if they exist in meta or root
        if (meta.boundary) {
            Object.assign(cleanConfig.boundary, meta.boundary);
        }

        // Core Payload
        return {
            scriptName: scriptName, // Filename (e.g., 'Script.py')
            rows: rows,
            token: token,
            envConfig: cleanConfig
        };
    }

    /**
     * Execute the script.
     * @returns {Promise<Array>} List of result objects
     */
    async execute(scriptName, rows, token, envConfig, meta = {}) {
        if (!scriptName) throw new Error('Script Name is required');
        if (!rows || rows.length === 0) throw new Error('No data rows to process');
        if (!token) throw new Error('Auth Token is missing');

        const payload = this.preparePayload(scriptName, rows, token, envConfig, meta);

        if (this.debug) {
            console.log('[ExecutorV2] Payload:', payload);
        }

        try {
            const endpoint = `${this.apiBaseUrl}/api/scripts/execute`; // Use local proxy if base is empty, or full URL
            // Actually, in this app, we call our own Node backend which proxies/executes.
            // So we usually call '/api/scripts/execute' relative to current origin.
            const url = '/api/scripts/execute';

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                    // 'Authorization': `Bearer ${token}` // Backend handles auth with python args, but we can send here too if needed
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || `Execution failed with status ${response.status}`);
            }

            const results = await response.json();

            // Standardization: Ensure Array
            if (Array.isArray(results)) {
                return results;
            } else if (results.status) {
                // Single object response? Wrap it.
                return [results];
            } else {
                console.warn('[ExecutorV2] Unexpected response format:', results);
                return results; // Return as is, let caller handle
            }

        } catch (error) {
            console.error('[ExecutorV2] Execution Error:', error);
            throw error; // Re-throw for UI to handle
        }
    }
}

// Attach to window for global access
window.ScriptExecutorV2 = ScriptExecutorV2;
