var map;

function centerMap() {
    if (!map || map._loaded) {
        if ("geolocation" in navigator) {
            navigator.geolocation.getCurrentPosition(function(position) {
                var lat = position.coords.latitude;
                var lon = position.coords.longitude;

                if (!map) {
                    map = L.map('map').setView([lat, lon], 13);
                    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                        attribution: '© OpenStreetMap contributors'
                    }).addTo(map);
                    updateTraffic();  // Llama a la función para actualizar el tráfico
                } else {
                    map.setView([lat, lon], 13);
                }
            }, function(error) {
                console.error("Error obteniendo la ubicación del usuario:", error);
                map.setView([40, -74.5], 9);
            });
        } else {
            map.setView([40, -74.5], 9);
            console.error("Geolocalización no compatible en este navegador");
        }
    }
}

// Actualizar data del trafico en mapa

function updateTraffic() {
    fetch('/get_traffic_data')
        .then(response => response.json())
        .then(data => {
            console.log('Datos recibidos:', data);
            // Limpiar los marcadores existentes en el mapa
            map.eachLayer(layer => {
                if (layer instanceof L.Marker) {
                    layer.remove();
                }
            });

            // Procesar los datos y agregar nuevos marcadores al mapa
            data.forEach(flight => {
                var marker = L.marker([flight.latitude, flight.longitude]).addTo(map);
                marker.bindPopup(`
                    Flight: ${flight.callsign}<br>
                    Latitude: ${flight.latitude}<br>
                    Longitude: ${flight.longitude}<br>
                    Altitude: ${flight.altitude}<br>
                    Velocity: ${flight.velocity}
                `);
            });
        })
        .catch(error => console.error("Error obteniendo datos de tráfico:", error));
}

centerMap();
