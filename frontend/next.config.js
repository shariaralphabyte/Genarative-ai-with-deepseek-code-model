/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8080/api/:path*',
      },
    ]
  },
  // Increase timeout for API routes
  experimental: {
    proxyTimeout: 10 * 60 * 1000, // 10 minutes
  },
}

module.exports = nextConfig
