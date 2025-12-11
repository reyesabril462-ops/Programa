from flask import Flask, render_template, request, jsonify, redirect, session, url_for, flash, g, send_from_directory
import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "Clavesuperhipermegasupremaparaguardarcosasydemascosasenlasessionyensecreto"


db = mysql.connector.connect(
    host="Localhost",
    user="root",
    password="",
    database="proyecto"
)

# RUTA DE INICIO
@app.route("/", methods=["GET", "POST"])
def inicio():
    return redirect(url_for("login_alumnos"))

@app.route("/login/inicial", mehtods=['GET', 'POST'])
def login_inicial():
    if request.mehtod == "POST":
        usuario = request.form["usuario"]
        contrasena = request.form["contrasena"]
        if not usuario or not contrasena:
            flash("Por favor ingresa tu usuario y contraseña para poder acceder al sistema.")
            return redirect(url_for("login_inicial"))
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT contrasena WHERE usuario = %s", (usuario))

        if usuario and check_password_hash(usuario["contrasena"], contrasena):
            # Inicio de sesión exitoso
            session["usuario_usuario"] = usuario
            session["usuario_contrasena"] = contrasena["contrasena"]
            
            flash(f"Inicio de sesión exitoso. Bienvenido, {usuario["usuario"]}.")
            return redirect(url_for("menu_alumnos"))
        else:
            # Error de credenciales
            flash("Número de Control o CURP incorrectos.")
            return redirect(url_for("login_alumnos"))

    # Para peticiones GET, simplemente muestra el formulario
    return render_template("login/alumnos/login_alumnos_nuevo.html")


@app.route("/login/alumnos", methods=["GET", "POST"])
def login_alumnos():
    if request.method == "POST":
        numero_control = request.form.get("NumeroControl") # Viene del campo 'nocontrol' en HTML
        curp_ingresada = request.form.get("Curp")         # Viene del nuevo campo 'curp' en HTML

        if not numero_control or not curp_ingresada:
            flash("Por favor, ingresa tu Número de Control y CURP.")
            return redirect(url_for("login_alumnos"))

        # 2. CONSULTAR la base de datos
        # Buscamos por el NumeroControl y recuperamos el Nombre y el hash de la CURP almacenada.
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT Nombre, contrasena FROM alumnos WHERE NumeroControl = %s", (numero_control,))
        alumno = cursor.fetchone()
        cursor.close()

        # 3. VALIDAR
        # El alumno existe Y el hash de la CURP ingresada coincide con el hash almacenado.
        if alumno and check_password_hash(alumno["contrasena"], curp_ingresada):
            # Inicio de sesión exitoso
            session["alumno_nc"] = numero_control 
            session["alumno_nombre"] = alumno["Nombre"]
            
            flash(f"Inicio de sesión exitoso. Bienvenido, {alumno['Nombre']}.")
            return redirect(url_for("menu_alumnos"))
        else:
            # Error de credenciales
            flash("Número de Control o CURP incorrectos.")
            return redirect(url_for("login_alumnos"))

    # Para peticiones GET, simplemente muestra el formulario
    return render_template("login/alumnos/login_alumnos_nuevo.html")

# PARTE DEL LOGOUT 
# LOGOUT ALUMNOS
@app.route("/logout_alumnos")
def logout_alumnos():
    session.clear()  # Limpiamos toda la sesión
    flash("Has cerrado sesión exitosamente.")
    return redirect(url_for("login_alumnos"))

# LOGOUT DOCENTES
@app.route("/logout_docentes")
def logout_docentes():
    session.clear()  # Limpiamos toda la sesión
    flash("Has cerrado sesión exitosamente.")
    return redirect(url_for("login_docentes"))

# PARTE DEL REGISTRO
@app.route("/registro/alumnos", methods=["GET", "POST"])
def registro_alumnos():
    if request.method == "POST":
        try:
                nocontrol = request.form["nocontrol"]
                usuario = request.form["usuario"]
                correo = request.form["correo"]
                contrasena = request.form["contrasena"]
                contrasena_hash = generate_password_hash(contrasena)
                cursor = db.cursor()
                sql = "INSERT INTO alumnos (nocontrol, usuario, correo, contrasena) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (nocontrol, usuario, correo, contrasena_hash))
                db.commit()
                cursor.close()
                return redirect('/')
        except Exception as e:
            print("Error:", e)
            flash(f"Error en el registro. Por favor, intenta de nuevo {e}.")
            return redirect(url_for("registro_alumnos"))
    return render_template("registro/alumnos/registro_alumno.html")

# PARTE DEL MENU
@app.route("/menu/alumnos", methods=["GET", "POST"])
def menu_alumnos():
    if "alumno" not in session:
        flash("Debes iniciar sesión primero.")
        return redirect(url_for("login_alumnos"))
    return render_template("menus/menu_alumnos.html")


# PARTE DEL REGISTRO DE DOCENTES
@app.route("/registro/docentes", methods=["GET","POST"])
def registro_docente():
    if request.method == "POST":
        try:
            noempleado = request.form["noempleado"]
            materia = request.form["materia"]
            usuario = request.form["usuario"]
            correo = request.form["correo"]
            password = request.form["password"]
            numtelefono = request.form["numtelefono"]
            hashed_password = generate_password_hash(password)
            cursor = db.cursor()
            cursor.execute("INSERT INTO docentes (noempleado, materia, usuario, correo, contrasena, numtelefono) VALUES (%s, %s, %s, %s, %s, %s)", (noempleado, materia, usuario, correo, hashed_password, numtelefono))
            db.commit()
            cursor.close()
            return redirect(url_for("login_docentes"))
        except Exception as e:
            flash(f"Hubo un error {e}")
    return render_template("registro/docentes/registro_docente.html")


# PARTE DEL LOGIN DE DOCENTES
@app.route("/login/docentes", methods=["GET", "POST"])
def login_docentes():
    if request.method == "POST":
        noempleado = request.form["noempleado"]
        usuario = request.form["usuario"]
        contrasena = request.form["contrasena"]

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT noempleado, usuario, contrasena FROM docentes WHERE noempleado = %s AND usuario = %s", (noempleado, usuario))
        docente = cursor.fetchone()
        cursor.close()

        if docente and check_password_hash(docente["contrasena"], contrasena):
            session["docente"] = docente["usuario"]
            flash("Inicio de sesión exitoso.")
            return redirect(url_for("menu_docentes"))
        else:
            flash("Usuario o contraseña incorrectos.")
            return redirect(url_for("login_docentes"))

    return render_template("login/docentes/login_docentes.html")

# PARTE DEL MENU DE DOCENTES
@app.route("/menu/docentes", methods=["GET", "POST"])
def menu_docentes():
    if "docente" not in session:
        flash("Debes iniciar sesión primero.")
        return redirect(url_for("login_docentes"))
    return render_template("menus/menu_docentes.html")

# PARTE DE AYUDA
@app.route("/ayuda", methods=["GET"])
def ayuda():
    origen = request.args.get("from_", "login")  # por defecto viene del login
    session["origen_ayuda"] = origen
    return render_template("ayuda/ayuda.html")



@app.route("/volver/ayuda", methods=["GET"])
def volver_ayuda():
    origen = session.get("origen_ayuda", "login")
    if origen == "menu_alumnos":
        return redirect(url_for("menu_alumnos"))
    elif origen == "login_docentes":
        return redirect(url_for("login_docentes"))
    elif origen == "menu_docentes":
        return redirect(url_for("menu_docentes"))
    else:
        return redirect(url_for("login_alumnos"))

# PARTE DEL SISTEMA DE BORRADO Y EDICION DE DATOS.
# RUTA PARA EDITAR
@app.route('/editar/int<int:id>', methods=['GET','POST'])
def editar(id):
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        actividad = request.form['actividad']
        materia = request.form['materia']
        fecha = request.form['fecha']
        valor = request.form['valor']
        estado = request.form['estado']
        sql = "UPDATE actividades SET actividad=%s, materia=%s, fecha=%s, valor=%s, estado=%s WHERE id=%s"
        cursor.execute(sql, (actividad, materia, fecha, valor, estado, id))
        db.commit()
        cursor.close()
        return redirect(url_for('menu_docentes'))
# RUTA PARA ELIMINAR
@app.route('/eliminar/int<int:id>', methods=['GET'])
def eliminar(id):
    cursor = db.cursor()
    try:
        sql = "DELETE FROM actividades WHERE id=%s"
        cursor.execute(sql, (id,))
        db.commit()
        cursor.close()
        return redirect(url_for('menu_docentes'))
    except Exception as e:
        return f"Ha ocurrido un error: {e} :("


if __name__ == "__main__":
    app.run(debug=True)
