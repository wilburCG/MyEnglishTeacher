/** @type {import('next').NextConfig} */
// 注意（FW 踩坑）：INTERNAL_API_ORIGIN 在 next build 时烧进产物，改值必须重新 build
const apiOrigin = process.env.INTERNAL_API_ORIGIN || "http://localhost:8000";

const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiOrigin}/api/:path*` },
      { source: "/health", destination: `${apiOrigin}/health` },
    ];
  },
};

module.exports = nextConfig;
