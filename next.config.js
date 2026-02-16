/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'export',
    images: {
        unoptimized: true,
    },
    // GitHub Pages serves from a subdirectory matching the repo name
    basePath: '/ANTS-Invest',
    assetPrefix: '/ANTS-Invest',
    env: {
        BASE_PATH: '/ANTS-Invest',
    },
};

module.exports = nextConfig;
