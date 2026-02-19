# Use Node.js as the base image (Bookworm contains necessary libraries)
FROM node:20-bookworm-slim

# Install Python and system dependencies for geopandas
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libgdal-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package.json and requirements.txt first for caching
COPY package.json requirements.txt ./

# Install Node dependencies
# Note: postinstall script in package.json will run pip install
RUN npm install

# Copy the rest of the application
COPY . .

# Expose the port (Server.js uses 3001)
EXPOSE 3001

# Start the server
CMD ["npm", "start"]
