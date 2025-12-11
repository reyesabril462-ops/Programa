document.addEventListener("DOMContentLoaded", () => {
    const btnBuscar = document.getElementById("btn-buscar");
    const btnVoz = document.getElementById("btn-voz");
    const input = document.getElementById("buscador");
    const tbody = document.getElementById("tbody-alumnos");
    const resultadoVoz = document.getElementById("resultado-voz");

    // Store original alumnos data for text search fallback 
    let alumnosOriginales = [];

    // Extract initial alumnos from the rendered table 
    function capturarAlumnosOriginales() {
        alumnosOriginales = [];
        const rows = tbody.querySelectorAll("tr");
        rows.forEach(row => {
            const cells = row.querySelectorAll("td");
            if (cells.length >= 8) {
                alumnosOriginales.push({
                    NumeroControl: cells[0].textContent.trim(),
                    Curp: cells[1].textContent.trim(),
                    Nombre: cells[2].textContent.trim(),
                    Paterno: cells[3].textContent.trim(),
                    Materno: cells[4].textContent.trim(),
                    Turno: cells[5].textContent.trim(),
                    Grupo: cells[6].textContent.trim(),
                    Semestre: cells[7].textContent.trim()
                });
            }
        });
    }

    // --- ACTUALIZAR ESTADO DE CONEXIÓN DINÁMICO --- 
    function actualizarEstadoConexion() {
        if (!navigator.onLine) {
            btnVoz.textContent = "🔄 Voz (Whisper)";
            btnVoz.title = "Sin internet: Usa Whisper Python (servidor local)";
            resultadoVoz.textContent = "💡 Sin internet: Whisper Python listo (requiere servidor activo)";
        } else {
            btnVoz.textContent = "🎤 Voz (Online)";
            btnVoz.title = "Con internet: Web Speech API (alta calidad)";
            resultadoVoz.textContent = "";
        }
    }

    // Capturar alumnos al cargar 
    capturarAlumnosOriginales();
    actualizarEstadoConexion();
    window.addEventListener("online", actualizarEstadoConexion);
    window.addEventListener("offline", actualizarEstadoConexion);

    // --- FUNCIÓN PARA RENDERIZAR LA TABLA --- 
    function renderTabla(alumnos) {
        tbody.innerHTML = alumnos.map(a => ` 
            <tr> 
                <td>${a.NumeroControl}</td> 
                <td>${a.Curp}</td> 
                <td>${a.Nombre}</td> 
                <td>${a.Paterno}</td> 
                <td>${a.Materno}</td> 
                <td>${a.Turno}</td> 
                <td>${a.Grupo}</td> 
                <td>${a.Semestre}</td> 
                <td> 
                    <button type="button" onclick="window.location.href='/alumnos/editar/${a.NumeroControl}'" class="boton-zona">Editar</button> 
                    <form action="/docentes/alumnos/eliminar/${a.NumeroControl}" method="post" style="display:inline;"> 
                        <button type="submit" class="boton-logout" onclick="return confirm('¿Eliminar a ${a.Nombre} ${a.Paterno}?');">Eliminar</button> 
                    </form> 
                </td> 
            </tr> 
        `).join("");
    }

    // --- BÚSQUEDA LOCAL EN LA TABLA (fallback texto) --- 
    function buscarLocal(query) {
        const q = query.toLowerCase().trim();
        if (!q) return alumnosOriginales;

        return alumnosOriginales.filter(alumno => {
            return (
                alumno.NumeroControl.toLowerCase().includes(q) ||
                alumno.Nombre.toLowerCase().includes(q) ||
                alumno.Paterno.toLowerCase().includes(q) ||
                alumno.Materno.toLowerCase().includes(q) ||
                alumno.Grupo.toLowerCase().includes(q)
            );
        });
    }

    // --- EVENTOS --- 
    btnBuscar.addEventListener("click", buscar);
    input.addEventListener("keypress", (e) => {
        if (e.key === "Enter") buscar();
    });
    btnVoz.addEventListener("click", buscarPorVozInteligente);

    // --- BÚSQUEDA POR TEXTO --- 
    async function buscar() {
        const q = input.value.trim();
        if (!q) {
            alert("Escribe algo para buscar.");
            return;
        }

        try {
            const resp = await fetch(`/docentes/alumnos/buscar?q=${encodeURIComponent(q)}`);
            const data = await resp.json();

            if (data.error) {
                alert("⚠️ Error: " + data.error);
                return;
            }

            const alumnos = Array.isArray(data) ? data : [];
            if (!alumnos.length) {
                tbody.innerHTML = "<tr><td colspan='9'>No se encontraron resultados.</td></tr>";
            } else {
                renderTabla(alumnos);
            }
        } catch (err) {
            resultadoVoz.textContent = "⚠️ Sin conexión: búsqueda local.";
            const resultados = buscarLocal(q);
            if (!resultados.length) {
                tbody.innerHTML = "<tr><td colspan='9'>No se encontraron resultados.</td></tr>";
            } else {
                renderTabla(resultados);
            }
        }
    }

    // 🚀 BÚSQUEDA INTELIGENTE: Online → Whisper (automático) 
    async function buscarPorVozInteligente() {
        if (navigator.onLine) {
            // 🎤 MODO ONLINE: Web Speech API (mejor calidad) 
            await buscarPorVozOnline();
        } else {
            // 🔄 MODO OFFLINE: Python Whisper (auxiliar) 
            await buscarPorVozWhisper();
        }
    }

    // 🎤 BUSCADOR ONLINE: Web Speech API (alta calidad) 
    async function buscarPorVozOnline() {
        if (!("SpeechRecognition" in window) && !("webkitSpeechRecognition" in window)) {
            // Fallback a Whisper si no soporta Web Speech 
            resultadoVoz.textContent = "🌐 Web Speech no disponible, usando Whisper...";
            return buscarPorVozWhisper();
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();

        recognition.lang = "es-MX";
        recognition.continuous = false;
        recognition.interimResults = false;

        btnVoz.disabled = true;
        btnVoz.textContent = "🎙️ Escuchando...";
        resultadoVoz.textContent = "🎤 Modo Online - Habla claramente...";

        recognition.onresult = async (event) => {
            const texto = event.results[0][0].transcript;
            input.value = texto;
            resultadoVoz.textContent = `"${texto}" (Online) → Buscando...`;

            // Buscar en servidor con texto reconocido 
            try {
                const resp = await fetch(`/docentes/alumnos/buscar?q=${encodeURIComponent(texto)}`);
                const data = await resp.json();
                const alumnos = Array.isArray(data) ? data : [];

                if (alumnos.length > 0) {
                    renderTabla(alumnos);
                    resultadoVoz.textContent = `"${texto}" (Online) → ${alumnos.length} resultado(s)`;
                } else {
                    tbody.innerHTML = "<tr><td colspan='9'>No se encontraron resultados para: \"" + texto + "\"</td></tr>";
                    resultadoVoz.textContent = `"${texto}" (Online) → Sin resultados`;
                }
            } catch (err) {
                // Fallback local si servidor falla 
                const resultados = buscarLocal(texto);
                renderTabla(resultados.length ? resultados : []);
                resultadoVoz.textContent = `"${texto}" (Online→Local) → ${resultados.length} resultado(s)`;
            }
        };

        recognition.onerror = (e) => {
            console.warn("Web Speech error:", e.error);
            if (e.error === "network" || e.error === "service-not-available") {
                resultadoVoz.textContent = "🌐 Error online, cambiando a Whisper...";
                buscarPorVozWhisper();
            } else {
                resultadoVoz.textContent = `⚠️ Error voz online: ${e.error}`;
                btnVoz.disabled = false;
                btnVoz.textContent = "🎤 Voz (Online)";
            }
        };

        recognition.onend = () => {
            btnVoz.disabled = false;
            btnVoz.textContent = "🎤 Voz (Online)";
        };

        recognition.start();
    }

    // 🔄 BUSCADOR OFFLINE: Python Whisper (auxiliar confiable) 
    async function buscarPorVozWhisper() {
        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                resultadoVoz.textContent = "❌ Micrófono no soportado.";
                return;
            }

            btnVoz.disabled = true;
            btnVoz.textContent = "🔴 Grabando...";
            resultadoVoz.textContent = "🔄 Modo Offline - Whisper Python (5s)";

            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000
                }
            });

            const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
            const audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                stream.getTracks().forEach(track => track.stop());

                if (audioChunks.length === 0) {
                    resultadoVoz.textContent = "⚠️ Sin audio grabado.";
                    btnVoz.disabled = false;
                    btnVoz.textContent = navigator.onLine ? "🎤 Voz (Online)" : "🔄 Voz (Whisper)";
                    return;
                }

                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                resultadoVoz.textContent = "⏳ Whisper Python procesando...";

                const formData = new FormData();
                formData.append('audio', audioBlob, 'audio_whisper.webm');

                try {
                    const response = await fetch('/docentes/alumnos/buscar/voz/offline', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) throw new Error(`HTTP ${response.status}`);

                    const data = await response.json();

                    if (data.error) {
                        resultadoVoz.textContent = `❌ Whisper: ${data.error}`;
                        return;
                    }

                    const texto = data.texto || '';
                    if (texto) {
                        input.value = texto;
                        resultadoVoz.textContent = `"${texto}" (Whisper) → ${data.resultados.length} resultado(s)`;

                        if (data.resultados.length > 0) {
                            renderTabla(data.resultados);
                        } else {
                            tbody.innerHTML = "<tr><td colspan='9'>No se encontraron resultados para: \"" + texto + "\"</td></tr>";
                        }
                    } else {
                        resultadoVoz.textContent = "⚠️ Whisper no reconoció texto claro.";
                    }
                } catch (error) {
                    resultadoVoz.textContent = `❌ Error Whisper: ${error.message}. Verifica servidor Flask.`;
                } finally {
                    btnVoz.disabled = false;
                    btnVoz.textContent = navigator.onLine ? "🎤 Voz (Online)" : "🔄 Voz (Whisper)";
                }
            };

            // Grabar 5 segundos automáticamente 
            mediaRecorder.start();
            setTimeout(() => {
                if (mediaRecorder.state === 'recording') {
                    mediaRecorder.stop();
                    resultadoVoz.textContent = "⏹️ Procesando con Whisper...";
                }
            }, 5000);

        } catch (error) {
            resultadoVoz.textContent = `❌ Error micrófono: ${error.message}`;
            btnVoz.disabled = false;
            btnVoz.textContent = navigator.onLine ? "🎤 Voz (Online)" : "🔄 Voz (Whisper)";
        }
    }
});