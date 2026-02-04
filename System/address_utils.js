/**
 * Shared Address Utilities
 * Handles communication with the backend geocoding proxy.
 * Note: The backend /api/geocode already parses Google's response into the specific JSON structure 
 * (country, administrativeAreaLevel1, etc.) expected by the application.
 */

/**
 * Fetches geocoding data from the backend proxy.
 * Can be used by any script requiring address normalization.
 * 
 * @param {string} addressText - The address string to geocode
 * @param {number|null} lat - Optional latitude (if reverse geocoding)
 * @param {number|null} lng - Optional longitude (if reverse geocoding)
 * @returns {Promise<object>} - The geocoded address JSON or empty object if failed
 */
async function getGeocodedAddress(addressText, lat = null, lng = null) {
    if (!addressText && (lat === null || lng === null)) {
        return {};
    }

    try {
        const payload = {};
        if (addressText) payload.address = addressText;
        if (lat !== null && lng !== null) {
            payload.lat = lat;
            payload.lng = lng;
        }

        const response = await fetch('/api/geocode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            return await response.json();
        }
    } catch (e) {
        console.warn('Geocoding failed:', e);
    }
    return {};
}

// Global Export
if (typeof window !== 'undefined') {
    window.AddressUtils = {
        geocode: getGeocodedAddress
    };
}
