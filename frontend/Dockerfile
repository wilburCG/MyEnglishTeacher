FROM node:22-bookworm-slim

WORKDIR /app

ARG INTERNAL_API_ORIGIN=http://met-backend:8000
ENV INTERNAL_API_ORIGIN=${INTERNAL_API_ORIGIN}

COPY package.json ./
RUN npm install --registry=https://registry.npmmirror.com --no-audit --no-fund

COPY . .
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
