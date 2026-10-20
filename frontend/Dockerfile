FROM dhi.io/node:26-alpine3.23-dev AS builder
WORKDIR /app

COPY package.json .
COPY package-lock.json .
RUN npm ci .

COPY . .
RUN npm run build

FROM dhi.io/nginx:1-alpine3.23 AS runtime
WORKDIR /usr/share/nginx/html

COPY --from=builder /app/build /usr/share/nginx/html

EXPOSE 8080
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]