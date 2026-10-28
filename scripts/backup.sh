#!/bin/sh
# Copia de seguridad de Postgres (pg_dump comprimido) y borrado de las mas viejas de KEEP_DAYS dias.
# Cron diario:  30 3 * * * cd /opt/radar && ./scripts/backup.sh
# Restaurar:    gunzip -c backups/radar-AAAAMMDD-HHMM.sql.gz | docker compose exec -T db psql -U radar radar
set -e
DIR="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
mkdir -p "$DIR"
file="$DIR/radar-$(date +%Y%m%d-%H%M).sql.gz"
docker compose exec -T db pg_dump -U radar --no-owner radar | gzip >"$file.part"
mv "$file.part" "$file"
find "$DIR" -name 'radar-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
echo "Copia creada: $file ($(du -h "$file" | cut -f1))"
