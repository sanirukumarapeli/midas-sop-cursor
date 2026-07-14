/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/chat',
        destination: 'http://127.0.0.1:8000/api/chat', // Proxies traffic to your FastAPI backend
      },
    ];
  },
};

export default nextConfig;