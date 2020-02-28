FROM nginx:stable
COPY nginx.conf /etc/nginx/conf.d/default.conf
ADD html.tar.gz /srv/helpcenter
