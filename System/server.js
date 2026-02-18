const express = require('express');
const path = require('path');
const cors = require('cors');
const bodyParser = require('body-parser');

const app = express();
const PORT = 3001; // Running on a separate port

app.use(cors());
app.use(bodyParser.json({ limit: '50mb' }));
app.use(bodyParser.urlencoded({ limit: '50mb', extended: true }));

// Serve static files from current directory
// Serve static files from ROOT directory (parent of System)
app.use(express.static(path.join(__dirname, '..')));

// Import Backend Logic
require('../backend/api')(app);

// Default route
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, '..', 'script_management.html'));
});

app.listen(PORT, () => {
    console.log(`\n==================================================`);
    console.log(`✅ Data Generate Server running on http://localhost:${PORT}`);
    console.log(`📂 SERVING FROM: ${__dirname}`);
    console.log(`==================================================\n`);
});
