from flask import Blueprint, Flask, render_template, request, jsonify, redirect, session, url_for, flash, g, send_from_directory, current_app
import mysql.connector 
from werkzeug.security import check_password_hash, generate_password_hash 
from functools import wraps 
from werkzeug.utils import secure_filename 
import os 
import shutil 
import time 
from datetime import timedelta 
import speech_recognition as sr 
from flask_socketio import SocketIO, emit 
import subprocess 
import traceback # Importar traceback para depuración 
from datetime import datetime 
 
 
# Intentar importar Vosk para reconocimiento offline 
try: 
    from vosk import Model, KaldiRecognizer 
    import json 
    VOSK_AVAILABLE = True 
except ImportError: 
    VOSK_AVAILABLE = False 
 
 
app = Flask(__name__) 
app.secret_key = "Clavesuperhipermegasupremaparaguardarcosasydemascosasenlasessionyensecreto" 
socketio = SocketIO(app) 
 
# Optional cached Whisper (Python) model - loaded on first use if available 
WHISPER_PY_MODEL = None 
 
# Configuración de subidas (al inicio de tu archivo Flask) 
UPLOAD_FOLDER = 'uploads/entregas_alumnos' 
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'zip', 'rar', 'mp4', 'mp3', 'avi', 'mkv'} 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER 
 
 
# ✅ VERSIÓN CORRECTA (una sola línea) 
def allowed_file(filename): 
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS 
 
# Configuración de SESIÓN 
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=5) 
app.permanent_session_lifetime = timedelta(minutes=5) 
 
# Conexión a la Base de Datos 
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="materias_db"
    )
db = get_db_connection()
 
# ----------------------------------------------------- 
# --- DECORADORES SIMPLIFICADOS ----------------------- 
# ----------------------------------------------------- 
 
# Decorador para rutas que solo alumnos logueados pueden ver 
def login_required_alumno(f): 
    @wraps(f) 
    def decorated_function(*args, **kwargs): 
        if "alumno_nc" not in session: 
            flash("Debes iniciar sesión como alumno primero.") 
            return redirect(url_for("login_alumnos")) 
        return f(*args, **kwargs) 
    return decorated_function 
 
# Decorador para rutas que solo docentes logueados pueden ver 
def login_required_docente(f): 
    @wraps(f) 
    def decorated_function(*args, **kwargs): 
        if "docente" not in session: 
            flash("Debes iniciar sesión como docente primero.") 
            return redirect(url_for("login_docentes")) 
        return f(*args, **kwargs) 
    return decorated_function 
 
# Decorador para rutas públicas (accesibles sin sesión) 
def public_access(f): 
    @wraps(f) 
    def decorated_function(*args, **kwargs): 
        return f(*args, **kwargs) 
    return decorated_function 
 
# Decorador para rutas del chat 
def login_required_chat(f): 
    @wraps(f) 
    def decorated_function(*args, **kwargs): 
        if "docente" not in session and "alumno_nc" not in session: 
            flash("Acceso denegado: inicia sesión como alumno o docente para usar el chat.") 
            return redirect(url_for("menu_principal")) 
        return f(*args, **kwargs) 
    return decorated_function 
 
# Decorador del login generales 
def login_required(*roles): 
    def decorator(f): 
        @wraps(f) 
        def wrap(*args, **kwargs): 
            if "user_id" not in session: 
                flash("Inicia sesión primero", "error") 
                return redirect(url_for("login_general")) 
 
            if roles: 
                user_role = session.get("rol") 
                if user_role not in roles: 
                    # Provide clearer redirects depending on the current logged-in role 
                    if user_role == "alumno": 
                        flash("Ya estas registrado como alumno, cierra sesión e inicia sesión como docente", "error") 
                        return redirect(url_for("menu_alumnos")) 
                    elif user_role == "docente": 
                        flash("Ya estas registrado como docente, cierra sesión e inicia sesión como alumno", "error") 
                        return redirect(url_for("menu_docentes")) 
                    else: 
                        flash("No tienes permisos", "error") 
                        return redirect(url_for("login_general")) 
 
            return f(*args, **kwargs) 
        return wrap 
    return decorator 
 
 
# Ruta de inicio 
@app.route("/", methods=["GET", "POST"]) 
@public_access 
def inicio(): 
    return redirect(url_for("login_general")) 
 
# ----------------------------------------------------- 
# --- RUTAS DE ALUMNOS ------------------------------- 
# ----------------------------------------------------- 
 
# Menú de alumnos 
@app.route("/menu/alumnos", methods=["GET", "POST"]) 
@login_required("alumno") 
def menu_alumnos(): 
    alumno = session.get("nombre_completo") or session.get("usuario") or session.get("alumno_nombre") or session.get("docente") or session.get("alumno_nc") or "Usuario" 
    return render_template("menus/menu_alumnos.html", alumno=alumno) 
 
# Actividades de alumnos 
# Actividades de alumnos (ahora con botón de entrega) 
@app.route("/actividades/alumnos", methods=['GET']) 
@login_required("alumno") 
def actividades_alumnos(): 
    alumno_nc = session.get("user_id") # O el nombre de la variable de sesión para el NumeroControl del alumno 
    if not alumno_nc: 
        flash("Número de control de alumno no encontrado en sesión.", "error") 
        return redirect(url_for("login_general")) 
 
    try: 
        cursor = db.cursor(dictionary=True) 
        # Seleccionar todas las actividades 
        cursor.execute("SELECT numero_actividad, nombre, maestro, fecha_entrega, estado FROM actividades ORDER BY fecha_entrega DESC") 
        actividades = cursor.fetchall() 
 
        # Obtener las actividades que este alumno ya entregó 
        cursor.execute("SELECT numero_actividad FROM entregas_actividades WHERE numero_control_alumno = %s", (alumno_nc,)) 
        entregadas_por_alumno = {row['numero_actividad'] for row in cursor.fetchall()} 
 
        cursor.close() 
         
        for actividad in actividades: 
            actividad['estado_actual'] = get_activity_status(actividad['fecha_entrega']) 
            actividad['fecha_display'] = actividad['fecha_entrega'].strftime('%d/%m/%Y %H:%M') if isinstance(actividad['fecha_entrega'], datetime) else actividad['fecha_entrega'] 
            actividad['ya_entregada'] = actividad['numero_actividad'] in entregadas_por_alumno 
             
        return render_template("actividades/alumnos/actividades_alumnos.html", actividades=actividades) 
    except Exception as e: 
        flash(f"Ha ocurrido un error al cargar actividades: {e}") 
        actividades = [] 
        return render_template("actividades/alumnos/actividades_alumnos.html", actividades=actividades) 
 
# Ruta para que el alumno suba su actividad 
@app.route("/actividades/alumnos/subir/<int:numero_actividad>", methods=['POST']) 
@login_required("alumno") 
def subir_actividad_alumno(numero_actividad): 
    alumno_nc = session.get("user_id") # O la variable de sesión correcta 
    if not alumno_nc: 
        flash("Número de control de alumno no encontrado en sesión.", "error") 
        return redirect(url_for("login_general")) 
 
    if 'archivo' not in request.files: 
        flash('No se seleccionó ningún archivo.', 'error') 
        return redirect(url_for('actividades_alumnos')) 
     
    file = request.files['archivo'] 
    if file.filename == '': 
        flash('No se seleccionó ningún archivo.', 'error') 
        return redirect(url_for('actividades_alumnos')) 
 
    try: 
        cursor = db.cursor(dictionary=True) 
        cursor.execute("SELECT fecha_entrega FROM actividades WHERE numero_actividad = %s", (numero_actividad,)) 
        actividad = cursor.fetchone() 
        cursor.close() 
 
        if not actividad: 
            flash("La actividad no existe.", "error") 
            return redirect(url_for('actividades_alumnos')) 
         
        # Verificar estado: Solo si la actividad está "Activa" se permite subir 
        if get_activity_status(actividad['fecha_entrega']) == "Inactivo": 
            flash("Esta actividad ya está inactiva y no se pueden realizar entregas.", "error") 
            return redirect(url_for('actividades_alumnos')) 
         
        if file and allowed_file(file.filename): 
            filename = secure_filename(file.filename) 
            # Crear la carpeta de subida si no existe 
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], str(numero_actividad))
            os.makedirs(upload_path, exist_ok=True) 
             
            # Guardar el archivo en el servidor 
            file.save(os.path.join(upload_path, f"{alumno_nc}_{filename}")) # Nombramos el archivo con el NC del alumno 
             
            # Registrar la entrega en la base de datos 
            cursor = db.cursor() 
            sql = """ 
                INSERT INTO entregas_actividades (numero_actividad, numero_control_alumno, nombre_archivo_original, ruta_archivo_servidor) 
                VALUES (%s, %s, %s, %s) 
            """ 
            cursor.execute(sql, (numero_actividad, alumno_nc, filename, os.path.join(upload_path, f"{alumno_nc}_{filename}"))) 
            db.commit() 
            cursor.close() 
 
            flash('Actividad entregada exitosamente.', 'success') 
            return redirect(url_for('actividades_alumnos')) 
        else: 
            flash('Tipo de archivo no permitido.', 'error') 
            return redirect(url_for('actividades_alumnos')) 
 
    except Exception as e: 
        flash(f"Error al subir actividad: {e}", "error") 
        return redirect(url_for('actividades_alumnos')) 
     
# Calificaciones de alumnos 
@app.route("/calificaciones/alumnos", methods=['GET', 'POST']) 
@login_required("alumno") 
def calificaciones_alumnos(): 
    try: 
        cursor = db.cursor(dictionary=True) 
        cursor.execute("SELECT * FROM calificaciones_alumnos") 
        calificaciones = cursor.fetchall() 
        cursor.close() 
    except Exception as e: 
        flash(f"Ha ocurrido un error: {e}") 
        calificaciones = [] 
    return render_template("calificaciones/alumnos/calificaciones_alumnos.html", calificaciones=calificaciones) 
 
# Logout de alumnos 
@app.route("/logout/alumnos") 
@public_access 
def logout_alumnos(): 
    session.clear() 
    flash("Has cerrado sesión exitosamente.") 
    return redirect(url_for("login_general")) 
 
 
# Logout de docentes (compatibilidad con menús antiguos) 
@app.route("/logout/docentes") 
@public_access 
def logout_docentes(): 
    session.clear() 
    flash("Has cerrado sesión exitosamente.") 
    return redirect(url_for("login_general")) 
 
# ----------------------------------------------------- 
# --- RUTAS DE DOCENTES ------------------------------ 
# ----------------------------------------------------- 
 
# Menú de docentes 
@app.route("/menu/docentes", methods=["GET", "POST"]) 
@login_required("docente") 
def menu_docentes(): 
    docente = session.get("nombre_completo") or session.get("usuario") or session.get("docente") or session.get("alumno_nombre") or "Usuario" 
    return render_template("menus/menu_docentes.html", docente=docente) 
 
# ----------------------------------------------------- 
# --- RUTAS GENERALES ------------------------------- 
# ----------------------------------------------------- 
 
 
 
 
 
# Ruta de ayuda 
@app.route("/ayuda", methods=["GET"]) 
@public_access 
def ayuda(): 
    origen = request.args.get("from_", "login_general") 
    session["origen_ayuda"] = origen 
    return render_template("ayuda/ayuda.html") 
 
@app.route("/volver/ayuda", methods=["GET"]) 
@public_access 
def volver_ayuda(): 
    origen = session.get("origen_ayuda", "login_general") 
    ruta_origen = { 
        "login_general": "login_general", 
        "registro_general": "registro_general", 
        "menu_alumnos": "menu_alumnos", 
        "menu_docentes": "menu_docentes", 
    } 
    return redirect(url_for(ruta_origen.get(origen, "login_general"))) 
 
# ----------------------------------------------------- 
# --- RUTAS DE RECUPERACIÓN DE CONTRASEÑA ----------- 
# ----------------------------------------------------- 
 
# Recuperación de Contraseña para Alumnos 
@app.route('/verificar/identidad', methods=['GET', 'POST']) 
@public_access 
def verificar_identidad(): 
    if request.method == "POST": 
        nocontrol = request.form['nocontrol'] 
        curp = request.form['curp']   
        cursor = db.cursor(dictionary=True) 
        cursor.execute("SELECT curp FROM alumnos_old_login WHERE nocontrol = %s", (nocontrol,)) 
        alumno = cursor.fetchone() 
        cursor.close() 
 
        if alumno and alumno['curp'] == curp: 
            session["nc_recuperacion_tmp"] = nocontrol 
            return redirect(url_for("cambiar_contraseña")) 
        else: 
            flash("Identidad no verificada, inténtalo de nuevo por favor.") 
            return redirect(url_for("verificar_identidad")) 
 
    return render_template("login/alumnos/verificacion_de_identidad.html") 
 
@app.route('/cambiar/contraseña', methods=['GET', 'POST']) 
@public_access 
def cambiar_contraseña(): 
    nocontrol = session.get("nc_recuperacion_tmp") 
    if not nocontrol: 
        return redirect(url_for("verificar_identidad")) 
     
    if request.method == "POST": 
        nueva_contrasena = request.form["nueva_contrasena"] 
        hash_contrasena = generate_password_hash(nueva_contrasena) 
        cursor = db.cursor() 
        cursor.execute("UPDATE alumnos_old_login SET contrasena = %s WHERE nocontrol = %s", (hash_contrasena, nocontrol)) 
        db.commit() 
        cursor.close() 
        session.pop("nc_recuperacion_tmp", None) 
        flash("¡Contraseña actualizada exitosamente! Ya puedes iniciar sesión.") 
        return redirect(url_for("menu_principal")) 
     
    return render_template("login/alumnos/cambiar_contraseña.html") 
 
# Función auxiliar para determinar el estado de la actividad (colócala al inicio de tu archivo Flask, después de las importaciones) 
def get_activity_status(fecha_entrega_data): 
    """Devuelve 'Activo' o 'Inactivo' basado en la fecha de entrega""" 
    if isinstance(fecha_entrega_data, str): 
        try: 
            fecha_entrega = datetime.strptime(fecha_entrega_data, '%Y-%m-%d %H:%M:%S') 
        except ValueError: 
            fecha_entrega = datetime.strptime(fecha_entrega_data, '%Y-%m-%dT%H:%M') 
    elif isinstance(fecha_entrega_data, datetime): 
        fecha_entrega = fecha_entrega_data 
    else: 
        return "Inactivo" 
 
    now = datetime.now() 
     
    # CAMBIO: Activo/Inactivo en lugar de Pendiente/Vencida 
    if now <= fecha_entrega: 
        return "Activo" 
    else: 
        return "Inactivo" 
 
# ----------------------------------------------------- 
# --- RUTAS DE ACTIVIDADES (DOCENTES) ----------------- 
# ----------------------------------------------------- 
  
@app.route("/actividades/docentes", methods=["GET", "POST"]) 
@login_required("docente") 
def actividades_docentes(): 
    if request.method == "POST": 
        try: 
            nombre = request.form.get("nombre") 
            maestro = request.form.get("maestro") 
            fecha_entrega = request.form.get("fecha_entrega") 
             
            # ✅ Estado: Activo/Inactivo (NO Pendiente) 
            estado = get_activity_status(fecha_entrega) 
 
            cursor = db.cursor() 
            sql = """ 
                INSERT INTO actividades (nombre, maestro, fecha_entrega, estado) 
                VALUES (%s, %s, %s, %s) 
            """ 
            cursor.execute(sql, (nombre, maestro, fecha_entrega, estado)) 
            db.commit() 
            cursor.close() 
            flash("✅ Actividad creada correctamente.") 
            return redirect(url_for("actividades_docentes")) 
        except Exception as e: 
            print(f"Error: {e}") 
            flash(f"Error: {e}") 
 
    # Mostrar actividades 
    cursor = db.cursor(dictionary=True) 
    cursor.execute("SELECT * FROM actividades ORDER BY numero_actividad DESC") 
    actividades = cursor.fetchall() 
    cursor.close() 
     
    # Calcular estado actual (Activo/Inactivo) 
    for act in actividades: 
        act['estado_actual'] = get_activity_status(act['fecha_entrega']) 
        # Formato legible para tabla 
        if isinstance(act['fecha_entrega'], datetime): 
            act['fecha_display'] = act['fecha_entrega'].strftime('%d/%m/%Y %H:%M') 
        else: 
            try: 
                dt = datetime.strptime(str(act['fecha_entrega']), '%Y-%m-%d %H:%M:%S') 
                act['fecha_display'] = dt.strftime('%d/%m/%Y %H:%M') 
            except: 
                act['fecha_display'] = str(act['fecha_entrega']) 
     
    return render_template("actividades/docentes/actividades_docentes.html", actividades=actividades) 
 
# --- RUTAS DE DOCENTES (nuevas rutas) --- 
 
@app.route("/docentes/actividades/entregas", methods=["GET"])
@login_required("docente")
def ver_entregas_docente():
    UPLOAD_FOLDER = 'uploads/entregas_alumnos'

    try:
        cursor = db.cursor(dictionary=True)

        # 1. Lista de actividades
        cursor.execute("SELECT numero_actividad, nombre FROM actividades ORDER BY nombre")
        actividades = cursor.fetchall()
        cursor.close()

        # 2. Filtros
        selected_actividad_id = request.args.get('actividad_id', type=int)
        selected_grupo = request.args.get('grupo', 'todos')

        entregas = []

        if selected_actividad_id:
            cursor = db.cursor(dictionary=True)

            query = """
                SELECT ea.id, ea.numero_actividad, a.nombre AS nombre_actividad,
                       ea.numero_control_alumno, 
                       al.Nombre, al.Paterno, al.Materno, al.Grupo,
                       ea.nombre_archivo_original, ea.ruta_archivo_servidor, ea.fecha_entrega
                FROM entregas_actividades ea
                JOIN actividades a ON ea.numero_actividad = a.numero_actividad
                JOIN alumnos al ON ea.numero_control_alumno = al.NumeroControl
                WHERE ea.numero_actividad = %s
            """
            params = [selected_actividad_id]

            # Filtro por grupo
            if selected_grupo != "todos":
                query += " AND al.Grupo = %s"
                params.append(selected_grupo)

            query += " ORDER BY al.Grupo, al.Nombre"

            cursor.execute(query, tuple(params))
            entregas = cursor.fetchall()
            cursor.close()

        # 3. Lista de grupos disponibles
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT DISTINCT Grupo FROM alumnos ORDER BY Grupo")
        grupos = [row['Grupo'] for row in cursor.fetchall()]
        cursor.close()

        # Preparar nombre del archivo
        for e in entregas:
            ruta = e.get('ruta_archivo_servidor') or ""
            e['download_filename'] = os.path.basename(ruta) if ruta else ""

        return render_template(
            "actividades/docentes/ver_entregas.html",
            actividades=actividades,
            entregas=entregas,
            grupos=['todos'] + grupos,
            selected_actividad_id=selected_actividad_id,
            selected_grupo=selected_grupo,
            upload_folder=UPLOAD_FOLDER
        )

    except Exception as e:
        print(f"Error al cargar entregas: {e}")
        flash(f"Error al cargar entregas: {e}", "error")
        return redirect(url_for('menu_docentes'))
 
# Ruta para descargar archivos de entrega (protegida para docentes) 
@app.route('/docentes/entregas/descargar/<int:numero_actividad>/<filename>') 
@login_required("docente") 
def descargar_entrega(numero_actividad, filename): 
    UPLOAD_FOLDER = 'uploads/entregas_alumnos'  # ✅ Local 
     
    # Ruta segura 
    safe_path = os.path.join(UPLOAD_FOLDER, str(numero_actividad), filename) 
     
    if os.path.exists(safe_path): 
        return send_from_directory(os.path.dirname(safe_path), filename, as_attachment=True) 
    else: 
        flash("Archivo no encontrado.", "error") 
        return redirect(url_for('ver_entregas_docente')) 
     
@app.route('/actividades/editar/<int:numero_actividad>', methods=['GET','POST']) 
@login_required("docente") 
def editar_actividad(numero_actividad): 
    cursor = None 
    try: 
        cursor = db.cursor(dictionary=True) 
         
        if request.method == 'POST': 
            nombre = request.form['nombre'].strip() 
            maestro = request.form['maestro'].strip() 
            fecha_entrega = request.form['fecha_entrega'].strip() 
             
            # ✅ Estado: Activo/Inactivo 
            estado = get_activity_status(fecha_entrega) 
             
            if not all([nombre, maestro, fecha_entrega]): 
                flash("Todos los campos son obligatorios.", "error") 
                return redirect(url_for('editar_actividad', numero_actividad=numero_actividad)) 
 
            sql = "UPDATE actividades SET nombre=%s, maestro=%s, fecha_entrega=%s, estado=%s WHERE numero_actividad=%s" 
            cursor.execute(sql, (nombre, maestro, fecha_entrega, estado, numero_actividad)) 
            db.commit() 
            flash("✅ Actividad actualizada.") 
            return redirect(url_for('actividades_docentes')) 
         
        cursor.execute("SELECT * FROM actividades WHERE numero_actividad = %s", (numero_actividad,)) 
        actividad = cursor.fetchone() 
         
        if not actividad: 
            flash("Actividad no encontrada.", "error") 
            return redirect(url_for('menu_docentes')) 
         
        # Formatear fecha para input datetime-local 
        if isinstance(actividad['fecha_entrega'], datetime): 
            actividad['fecha_entrega_formatted'] = actividad['fecha_entrega'].strftime('%Y-%m-%dT%H:%M') 
        else: 
            try: 
                dt = datetime.strptime(str(actividad['fecha_entrega']), '%Y-%m-%d %H:%M:%S') 
                actividad['fecha_entrega_formatted'] = dt.strftime('%Y-%m-%dT%H:%M') 
            except: 
                actividad['fecha_entrega_formatted'] = '' 
         
        return render_template('/actividades/docentes/editar_actividad.html', actividad=actividad) 
         
    except Exception as e: 
        flash(f"Error: {e}", "error") 
        return redirect(url_for('actividades_docentes')) 
    finally: 
        if cursor: 
            cursor.close() 
 
 
@app.route('/actividades/eliminar/<int:numero_actividad>', methods=['POST']) 
@login_required("docente") 
def eliminar_actividad(numero_actividad): 
    cursor = None 
    try: 
        cursor = db.cursor() 
         
        # Verifica que la actividad existe antes de eliminar 
        cursor.execute("SELECT numero_actividad FROM actividades WHERE numero_actividad = %s", (numero_actividad,)) 
        if not cursor.fetchone(): 
            flash("Actividad no encontrada.", "error") 
            return redirect(url_for('menu_docentes')) 
         
        sql = "DELETE FROM actividades WHERE numero_actividad=%s" 
        cursor.execute(sql, (numero_actividad,)) 
        db.commit() 
        flash("Actividad eliminada exitosamente.", "success") 
         
    except Exception as e: 
        print(f"Error al eliminar actividad: {e}") 
        flash(f"Error al eliminar actividad: {e}", "error") 
    finally: 
        if cursor: 
            cursor.close() 
    return redirect(url_for('menu_docentes')) 
 
 
 
# Función auxiliar para obtener la lista de alumnos (usada en múltiples rutas) 
def get_alumnos_from_db(): 
    cursor = db.cursor(dictionary=True) 
    cursor.execute("SELECT NumeroControl, Curp, Nombre, Paterno, Materno, Turno, Grupo, Semestre FROM alumnos ORDER BY NumeroControl") 
    alumnos = cursor.fetchall() 
    cursor.close() 
    return alumnos 
 
# Listar y Crear Alumnos (todo en una ruta) 
@app.route("/docentes/alumnos/gestion", methods=["GET", "POST"]) 
@login_required("docente") 
def gestionar_alumnos(): 
    cursor = None 
    try: 
        if request.method == "POST": # Lógica para añadir un alumno 
            numerocontrol = request.form["NumeroControl"].strip() 
            curp = request.form["Curp"].strip() 
            nombre = request.form["Nombre"].strip() 
            paterno = request.form["Paterno"].strip() 
            materno = request.form["Materno"].strip() 
            turno = request.form["Turno"].strip() 
            grupo = request.form["Grupo"].strip() 
            semestre = request.form["Semestre"].strip() 
 
            if not all([numerocontrol, curp, nombre, paterno, materno, turno, grupo, semestre]): 
                flash("Todos los campos son obligatorios.", "error") 
                return render_template("docentes/alumnos/lista_de_alumnos.html", alumnos=get_alumnos_from_db(), form_data=request.form) 
             
            cursor = db.cursor() 
            cursor.execute("SELECT 1 FROM alumnos WHERE NumeroControl = %s", (numerocontrol,)) 
            if cursor.fetchone(): 
                flash(f"El Número de Control '{numerocontrol}' ya existe.", "error") 
                cursor.close() 
                return render_template("docentes/alumnos/lista_de_alumnos.html", alumnos=get_alumnos_from_db(), form_data=request.form) 
            cursor.close() 
 
            cursor = db.cursor() # Re-abre el cursor 
            sql = """INSERT INTO alumnos (NumeroControl, Curp, Nombre, Paterno, Materno, Turno, Grupo, Semestre) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""" 
            cursor.execute(sql, (numerocontrol, curp, nombre, paterno, materno, turno, grupo, semestre)) 
            db.commit() 
            flash("Alumno creado exitosamente.", "success") 
            cursor.close() 
            return redirect(url_for("gestionar_alumnos")) # Redirige al GET para limpiar el formulario y actualizar la lista 
         
        # Lógica para listar alumnos (GET) 
        alumnos_data = get_alumnos_from_db() 
        return render_template("docentes/alumnos/lista_de_alumnos.html", alumnos=alumnos_data) 
    except Exception as e: 
        flash(f"Error al procesar la solicitud: {e}", "error") 
        return render_template("docentes/alumnos/lista_de_alumnos.html", alumnos=[]) 
    finally: 
        if cursor: 
            cursor.close() 
 
# Obtener el numero de control 
def get_alumno_by_numerocontrol(numerocontrol): 
    cursor = db.cursor(dictionary=True) 
    cursor.execute("SELECT * FROM alumnos WHERE NumeroControl = %s", (numerocontrol,)) 
    alumno = cursor.fetchone() 
    cursor.close() 
    return alumno 
 
 
# Editar alumno 
@app.route("/alumnos/editar/<string:numerocontrol>", methods=["GET", "POST"]) 
@login_required("docente") 
def editar_alumno(numerocontrol): 
    cursor = None 
    try: 
        cursor = db.cursor(dictionary=True) 
        alumno = get_alumno_by_numerocontrol(numerocontrol) 
 
        if not alumno: 
            flash("Alumno no encontrado.", "error") 
            return redirect(url_for("gestionar_alumnos")) 
 
        if request.method == "POST": 
            nombre = request.form.get("Nombre") 
            paterno = request.form.get("Paterno") 
            materno = request.form.get("Materno") 
            curp = request.form.get("Curp") 
            turno = request.form.get("Turno") 
            grupo = request.form.get("Grupo") 
            semestre = request.form.get("Semestre") 
 
            # Validación simple 
            if not all([nombre, paterno, materno, curp, turno, grupo, semestre]): 
                flash("Todos los campos son obligatorios.", "error") 
                return render_template("docentes/alumnos/editar_alumno.html", alumno=alumno) 
 
            # Actualizar en la DB 
            sql = """ 
                UPDATE alumnos 
                SET Nombre=%s, Paterno=%s, Materno=%s, Curp=%s, Turno=%s, Grupo=%s, Semestre=%s 
                WHERE NumeroControl=%s 
            """ 
            cursor.execute(sql, (nombre, paterno, materno, curp, turno, grupo, semestre, numerocontrol)) 
            db.commit() 
            flash("Alumno actualizado exitosamente.", "success") 
            return redirect(url_for("gestionar_alumnos")) 
 
        return render_template("docentes/alumnos/editar_alumno.html", alumno=alumno) 
 
    except Exception as e: 
        flash(f"Error al editar alumno: {e}", "error") 
        return redirect(url_for("gestionar_alumnos")) 
    finally: 
        if cursor: 
            cursor.close() 
 
 
# Eliminar alumno 
@app.route("/docentes/alumnos/eliminar/<string:numerocontrol>", methods=["POST"]) 
@login_required("docente") 
def eliminar_alumno(numerocontrol): 
    cursor = None 
    try: 
        cursor = db.cursor() 
        cursor.execute("SELECT 1 FROM alumnos WHERE NumeroControl = %s", (numerocontrol,)) 
        if not cursor.fetchone(): 
            flash(f"Alumno con Número de Control '{numerocontrol}' no encontrado.", "error") 
            return redirect(url_for("gestionar_alumnos")) 
         
        sql = "DELETE FROM alumnos WHERE NumeroControl = %s" 
        cursor.execute(sql, (numerocontrol,)) 
        db.commit() 
        flash("Alumno eliminado exitosamente.", "success") 
        return redirect(url_for("gestionar_alumnos")) 
    except Exception as e: 
        flash(f"Error al eliminar el alumno: {e}", "error") 
        return redirect(url_for("gestionar_alumnos")) 
    finally: 
        if cursor: 
            cursor.close() 
 
# Búsqueda por texto mejorada 
@app.route("/docentes/alumnos/buscar", methods=["GET"]) 
@login_required("docente") 
def buscar_alumnos(): 
    query = request.args.get("q", "").strip() 
    try: 
        cursor = db.cursor(dictionary=True) 
        alumnos = [] 
 
        if query: 
            palabras = query.split()  # Dividir el texto en palabras 
            condiciones = [] 
            parametros = [] 
 
            for palabra in palabras: 
                like = f"%{palabra}%" 
                # Cada palabra se compara con todas las columnas relevantes 
                condiciones.append("(NumeroControl LIKE %s OR Nombre LIKE %s OR Paterno LIKE %s OR Materno LIKE %s OR Grupo LIKE %s)") 
                parametros.extend([like, like, like, like, like]) 
 
            sql = f""" 
                SELECT NumeroControl, Curp, Nombre, Paterno, Materno, Turno, Grupo, Semestre 
                FROM alumnos 
                WHERE {" AND ".join(condiciones)} 
            """ 
            cursor.execute(sql, tuple(parametros)) 
            alumnos = cursor.fetchall() 
 
        cursor.close() 
        return jsonify(alumnos) 
    except Exception as e: 
        return jsonify({"error": str(e)}), 500 
 
 
# Búsqueda por voz mejorada 
@app.route("/docentes/alumnos/buscar/voz", methods=["POST"]) 
@login_required("docente") 
def buscar_alumnos_voz(): 
    recognizer = sr.Recognizer() 
    try: 
        if "audio" not in request.files: 
            return jsonify({"error": "No se envió ningún audio."}), 400 
 
        audio_file = request.files["audio"] 
        with sr.AudioFile(audio_file) as source: 
            audio_data = recognizer.record(source) 
 
        texto = recognizer.recognize_google(audio_data, language="es-MX") 
        palabras = texto.split() 
 
        cursor = db.cursor(dictionary=True) 
        condiciones = [] 
        parametros = [] 
 
        for palabra in palabras: 
            like = f"%{palabra}%" 
            condiciones.append("(NumeroControl LIKE %s OR Nombre LIKE %s OR Paterno LIKE %s OR Materno LIKE %s OR Grupo LIKE %s)") 
            parametros.extend([like, like, like, like, like]) 
 
        sql = f""" 
            SELECT NumeroControl, Curp, Nombre, Paterno, Materno, Turno, Grupo, Semestre 
            FROM alumnos 
            WHERE {" AND ".join(condiciones)} 
        """ 
        cursor.execute(sql, tuple(parametros)) 
        alumnos = cursor.fetchall() 
        cursor.close() 
 
        return jsonify({"texto": texto, "resultados": alumnos}) 
 
    except sr.UnknownValueError: 
        return jsonify({"error": "No se entendió el audio, intenta de nuevo."}), 400 
    except Exception as e: 
        return jsonify({"error": f"Error al procesar el audio: {e}"}), 500 
 
 
@app.route("/docentes/alumnos/buscar/voz/offline", methods=["POST"]) 
@login_required("docente") 
def buscar_alumnos_voz_offline(): 
    try: 
        # Recibir audio 
        audio_file = request.files["audio"] 
        tmp_dir = os.path.join(os.path.dirname(__file__), 'tmp') 
        os.makedirs(tmp_dir, exist_ok=True) 
        tmp_path = os.path.join(tmp_dir, f"audio_{int(time.time())}.webm") 
         
        with open(tmp_path, 'wb') as f: 
            f.write(audio_file.read()) 
        print(f"📁 Audio: {tmp_path}") 
 
        # Modelo TINY (baja RAM, ~500MB) 
        global WHISPER_PY_MODEL 
        if WHISPER_PY_MODEL is None: 
            print("🧠 Cargando tiny (baja RAM)...") 
            import whisper 
            WHISPER_PY_MODEL = whisper.load_model("tiny") 
            print("✅ Tiny listo (~500MB RAM)") 
 
        # Transcribir 
        print("🎵 Transcribiendo...") 
        result = WHISPER_PY_MODEL.transcribe(tmp_path, language='es', fp16=False) 
        texto = result["text"].strip() 
        print(f"✅ Texto: '{texto}'") 
 
        # Búsqueda inteligente en BD (múltiples palabras) 
        cursor = db.cursor(dictionary=True) 
        palabras = texto.split() 
        condiciones = [] 
        params = [] 
         
        for palabra in palabras[:3]:  # Máximo 3 palabras para no sobrecargar 
            like = f"%{palabra}%" 
            condiciones.append("(NumeroControl LIKE %s OR Nombre LIKE %s OR Paterno LIKE %s OR Grupo LIKE %s)") 
            params.extend([like, like, like, like]) 
         
        if condiciones: 
            sql = f""" 
                SELECT NumeroControl, Curp, Nombre, Paterno, Materno, Turno, Grupo, Semestre 
                FROM alumnos WHERE {' AND '.join(condiciones)} 
                ORDER BY NumeroControl LIMIT 20 
            """ 
            cursor.execute(sql, params) 
            alumnos = cursor.fetchall() 
        else: 
            alumnos = [] 
             
        cursor.close() 
        os.unlink(tmp_path) 
 
        print(f"✅ Tiny: '{texto}' → {len(alumnos)} resultados") 
        return jsonify({ 
            "texto": texto,  
            "resultados": alumnos,  
            "modo": "whisper_tiny" 
        }) 
         
    except Exception as e: 
        print(f"💥 Tiny error: {e}") 
        return jsonify({"error": str(e)}), 500 
     
# Endpoint temporal para descargar archivos de diagnóstico desde tmp/ 
@app.route('/tmp/<path:filename>') 
@login_required('docente') 
def download_tmp_file(filename): 
    """Descarga archivos de diagnóstico guardados en tmp/. Protegido para docentes.""" 
    try: 
        tmp_dir = os.path.join(os.path.dirname(__file__), 'tmp') 
        safe_name = os.path.basename(filename) 
        file_path = os.path.join(tmp_dir, safe_name) 
        if not os.path.exists(file_path): 
            return jsonify({"error": "Archivo no encontrado."}), 404 
        return send_from_directory(tmp_dir, safe_name, as_attachment=True) 
    except Exception as e: 
        print(f"[ERROR] download_tmp_file: {e}") 
        return jsonify({"error": f"Error al descargar archivo: {e}"}), 500 
 
# ----------------------------------------------------- 
# --- RUTAS DE INACTIVIDAD --------------------------- 
# ----------------------------------------------------- 
 
# Logout por inactividad 
@app.route("/logout_inactividad") 
@public_access 
def logout_inactividad(): 
    session.clear() 
    flash("Sesión cerrada por inactividad. Por favor, inicia sesión nuevamente.") 
    return redirect(url_for("login_general")) 
 
@app.route("/logout_general") 
@public_access 
def logout_general(): 
    session.clear() 
    flash("Has cerrado sesión exitosamente.") 
    return redirect(url_for("login_general")) 
 
 
# ----------------------------------------------------- 
# ---- RUTAS GENERALES -------------------------------- 
# ----------------------------------------------------- 
 
# Ruta del chat general 
@app.route("/chat/general", methods=["GET"]) 
@login_required() 
def chat_general(): 
    # Detectar tipo de usuario 
    usuario = session.get("nombre_completo", "Invitado") 
    rol = session.get("rol", "ninguno") 
 
    # Leer los mensajes guardados 
    cursor = db.cursor(dictionary=True) 
    cursor.execute("SELECT usuario, tipo_usuario, mensaje FROM chat_general ORDER BY id ASC") 
    mensajes = cursor.fetchall() 
 
    return render_template( 
        "chat_general/chat_general.html", 
        usuario=usuario, 
        tipo=rol, 
        mensajes=mensajes 
    ) 
 
 
# Evento de envío de mensajes 
@socketio.on("mensaje") 
@login_required() 
def manejar_mensaje(data): 
    usuario = session.get("nombre_completo", "Invitado") 
    tipo = session.get("rol", "ninguno") 
 
    mensaje = data["texto"] 
 
    # Guardar en la base de datos (usando la conexión global db) 
    cursor = db.cursor() 
    cursor.execute( 
        "INSERT INTO chat_general (usuario, tipo_usuario, mensaje) VALUES (%s, %s, %s)", 
        (usuario, tipo, mensaje) 
    ) 
    db.commit() 
 
    # Enviar mensaje a todos los conectados 
    emit("nuevo_mensaje", {"usuario": usuario, "tipo": tipo, "texto": mensaje}, broadcast=True) 
 
 
# ----------------------------------------------------- 
# --- SISTEMA PARA RECONOCER QUE TIPO DE USUARIO ES. -- 
# ----------------------------------------------------- 
@app.route("/volver/menus", methods=["GET"]) 
def volver_menus(): 
    # Verificar el rol del usuario 
    rol = session.get("rol", "") 
    if rol == "alumno": 
        return redirect(url_for("menu_alumnos")) 
    elif rol == "docente": 
        return redirect(url_for("menu_docentes")) 
    elif rol == "directivo": 
        return redirect(url_for("menu_directivo")) if "menu_directivo" in globals() else redirect(url_for("login_general")) 
    else: 
        return redirect(url_for("login_general")) 
     
 
# ----------------------------------------------------- 
# --- RUTA DE LOGIN GENERAL --------------------------- 
# ----------------------------------------------------- 
@app.route("/login/general", methods=["GET", "POST"]) 
def login_general(): 
    if request.method == "POST": 
        identificador = request.form.get("usuario") 
        password = request.form.get("contrasena") 
 
        conn = db 
        cursor = conn.cursor() 
 
        cursor.execute(""" 
            SELECT id, usuario, correo, contrasena, rol, nombre_completo 
            FROM usuarios 
            WHERE usuario=%s OR correo=%s 
        """, (identificador, identificador)) 
 
        row = cursor.fetchone() 
 
        if not row: 
            flash("Usuario o correo no existe", "error") 
            return redirect(url_for("login_general")) 
 
        user_id, db_user, db_correo, db_pass, db_rol, db_nombre = row 
 
        if not check_password_hash(db_pass, password): 
            flash("Contraseña incorrecta", "error") 
            return redirect(url_for("login_general")) 
 
        session["user_id"] = user_id 
        session["usuario"] = db_user 
        session["correo"] = db_correo 
        session["rol"] = db_rol 
        session["nombre_completo"] = db_nombre 
 
        # Redirección por rol 
        if db_rol == "alumno": 
            return redirect(url_for("menu_alumnos")) 
        elif db_rol == "docente": 
            return redirect(url_for("menu_docentes")) 
        else: 
            # Para otros roles (directivo, administrativo), redirigir a un menú general si existe 
            flash("Bienvenido al sistema.", "success") 
            return redirect(url_for("menu_alumnos"))  # O puedes crear menus específicos para otros roles 
 
    return render_template("login/general/general.html") 
 
 
@app.route("/registro/general", methods=["GET", "POST"]) 
def registro_general(): 
    if request.method == "POST": 
        id_usuario = request.form.get("id") 
        usuario = request.form.get("usuario") 
        correo = request.form.get("correo") 
        password = request.form.get("contrasena") 
        confirmar = request.form.get("confirmar_contrasena") 
        rol = request.form.get("rol") 
        # Role-specific fields 
        grupo = request.form.get("grupo") 
        semestre = request.form.get("semestre") 
        materia = request.form.get("materia") 
 
        if password != confirmar: 
            flash("Las contraseñas no coinciden", "error") 
            return redirect(url_for("registro_general")) 
 
        hash_pw = generate_password_hash(password) 
 
        conn = db 
        cursor = conn.cursor() 
 
        cursor.execute("SELECT id FROM usuarios WHERE usuario=%s OR correo=%s OR id=%s", (usuario, correo, id_usuario)) 
        if cursor.fetchone(): 
            flash("Usuario, correo o número de control/empleado ya existe.", "error") 
            return redirect(url_for("registro_general")) 
 
        # Build INSERT dynamically to include role-specific columns 
        columns = ["id", "usuario", "correo", "contrasena", "rol"] 
        placeholders = ["%s"] * len(columns) 
        values = [id_usuario, usuario, correo, hash_pw, rol] 
 
        if rol == "alumno": 
            # expect grupo/semestre 
            columns.extend(["grupo", "semestre"]) 
            placeholders.extend(["%s", "%s"]) 
            values.extend([grupo, semestre]) 
        elif rol == "docente": 
            columns.append("materia") 
            placeholders.append("%s") 
            values.append(materia) 
 
        sql = f"INSERT INTO usuarios ({', '.join(columns)}) VALUES ({', '.join(placeholders)})" 
        cursor.execute(sql, tuple(values)) 
        conn.commit() 
 
        flash("Cuenta creada correctamente", "success") 
        return redirect(url_for("login_general")) 
 
    return render_template("registro/general/general.html") 
 
# ----------------------------------------------------- 
# --- PUNTO DE ENTRADA DE LA APLICACIÓN --------------- 
# ----------------------------------------------------- 
if __name__ == "__main__": 
    socketio.run(app, debug=True) 
# Se cambio la funcion 'app.run' por 'socketio.run' para que el chat funcione correctamente 