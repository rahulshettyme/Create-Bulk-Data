const fs = require('fs');
const path = require('path');

const draftsDir = path.join(__dirname, 'Draft Scripts');
const filename = 'Add_Asset_Tag.py';
const metaPath = path.join(draftsDir, filename + '.meta.json');

console.log(`Checking: ${metaPath}`);

if (fs.existsSync(metaPath)) {
    console.log("File exists.");
    try {
        let rawMeta = fs.readFileSync(metaPath, 'utf8');
        console.log(`Raw length: ${rawMeta.length}`);

        // Check first char
        console.log(`First char code: ${rawMeta.charCodeAt(0)}`);

        if (rawMeta.charCodeAt(0) === 0xFEFF) {
            console.log("BOM detected, stripping...");
            rawMeta = rawMeta.slice(1);
        }

        const meta = JSON.parse(rawMeta);
        console.log("JSON Parsed successfully.");
        console.log(`Description present? ${!!meta.description}`);
        console.log(`Description length: ${(meta.description || "").length}`);
        if (meta.description) console.log(`Preview: ${meta.description.substring(0, 50)}`);

    } catch (e) {
        console.error("Error parsing:", e.message);
    }
} else {
    console.error("File NOT found.");
}
