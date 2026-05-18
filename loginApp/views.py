import pyodbc
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.conf import settings
import random
from .utils import RutValidator
from datetime import datetime, date
from django.db import connection


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        ip = request.META.get('REMOTE_ADDR')

        print(f"=" * 50)
        print(f"DEBUG LOGIN - Email: '{email}', Password: '{password}'")
        print(f"=" * 50)

        try:
            conn = pyodbc.connect(
                'DRIVER={ODBC Driver 17 for SQL Server};'
                'SERVER=localhost;'
                'DATABASE=proyectoinformatico;'
                'Trusted_Connection=yes;'
            )
            cursor = conn.cursor()

            # LOGIN directo verificando password_hash
            print(f"DEBUG: Verificando login directo...")
            cursor.execute("""
                SELECT id_usuario, correo, nombre, rol, password_hash 
                FROM usuarios 
                WHERE correo = ? AND password_hash = ?
            """, (email, password))
            user_check = cursor.fetchone()

            if not user_check:
                print(f"DEBUG: Login fallido - credenciales incorrectas")
                # Registrar intento fallido usando SP
                cursor.execute("""
                    EXEC sp_registrar_log ?, ?, ?
                """, (
                    None,
                    f'Intento fallido: {email}',
                    ip
                ))
                conn.commit()

                return render(request, 'login.html', {
                    'error': 'Credenciales incorrectas'
                })

            print(f"DEBUG: Login exitoso - id={user_check[0]}, rol={user_check[3]}")

            # Usar datos ya obtenidos en user_check
            id_usuario = user_check[0]

            # LOGIN CORRECTO
            request.session['email'] = email

            # guardar intento exitoso usando SP
            cursor.execute("""
                EXEC sp_registrar_log ?, ?, ?
            """, (
                id_usuario,
                'Inicio sesión exitoso',
                ip
            ))
            conn.commit()

            # generar token
            token = str(random.randint(100000, 999999))

            # Usar datos ya obtenidos en user_check
            nombre_usuario = user_check[2] if user_check[2] else email.split('@')[0]
            rol = user_check[3]

            # DEBUG: Ver el rol real
            print(f"DEBUG ROL ORIGINAL: '{rol}'")
            rol = rol.strip().lower() if rol else ''
            print(f"DEBUG ROL PROCESADO: '{rol}'")

            # Guardar id_usuario y rol en sesión para control de acceso
            request.session['id_usuario'] = id_usuario
            request.session['rol'] = rol

            
            # COMENTADO: Envío de código verificador por email
            # Descomentar estas líneas para activar verificación 2FA

            cursor.execute('''
                INSERT INTO tokens_sesion (id_usuario, token, fecha_expiracion, usado, activo)
                VALUES (?, ?, DATEADD(MINUTE, 5, GETDATE()), 0, 1)
            ''', (id_usuario, token))
            conn.commit()

            # Renderizar template HTML para el correo (CSS en archivo externo)
            from django.template.loader import render_to_string
            html_message = render_to_string('email_verificacion.html', {
                'nombre_usuario': nombre_usuario,
                'token': token
            })

            send_mail(
                'Código de verificación',
                f'Tu código es: {token}',
                settings.EMAIL_HOST_USER,
                ['franco.silvaah@correoaiep.cl'],
                fail_silently=False,
                html_message=html_message
            )

            return redirect('token')
            

            # BYPASS: Login directo sin verificación de código
            request.session['autenticado'] = True

            # Redirección según rol (ya está en minúsculas)
            print(f"DEBUG REDIRECCION - ROL: '{rol}'")
            if rol == 'admin':
                return redirect('admin_dashboard')
            elif rol == 'docente':
                return redirect('docente_dashboard')
            elif rol == 'alumno':
                return redirect('alumno_dashboard')
            elif rol == 'apoderado':
                return redirect('apoderado_dashboard')
            else:
                print(f"DEBUG: Rol no reconocido, redirigiendo a home")
                return redirect('home')

        except Exception as e:
            return render(request, 'login.html', {
                'error': str(e)
            })

    return render(request, 'login.html')


def logout_view(request):
    request.session.flush()
    return redirect('login')


def token_view(request):
    if request.method == 'POST':
        token_ingresado = request.POST.get('token')
        email = request.session.get('email')

        if not email:
            return redirect('login')

        try:
            conn = pyodbc.connect(
                'DRIVER={ODBC Driver 17 for SQL Server};'
                'SERVER=localhost;'
                'DATABASE=proyectoinformatico;'
                'Trusted_Connection=yes;'
            )
            cursor = conn.cursor()

            cursor.execute("""
                SELECT t.token
                FROM tokens_sesion t
                JOIN usuarios u ON t.id_usuario = u.id_usuario
                WHERE t.token = ?
                AND u.correo = ?
                AND t.usado = 0
                AND t.fecha_expiracion > GETDATE()
            """, (token_ingresado, email))

            row = cursor.fetchone()

            if row:
                # marcar como usado
                cursor.execute("""
                    UPDATE tokens_sesion
                    SET usado = 1
                    WHERE token = ?
                """, (token_ingresado,))
                conn.commit()

                request.session['autenticado'] = True

                # Redirección según rol
                rol = request.session.get('rol')

                if rol == 'admin':
                    return redirect('admin_dashboard')
                elif rol == 'docente':
                    return redirect('docente_dashboard')
                else:
                    return redirect('login')

            else:
                return render(request, 'token.html', {
                    'error': 'Token inválido o expirado'
                })

        except Exception as e:
            return render(request, 'token.html', {
                'error': str(e)
            })

    return render(request, 'token.html')


def admin_dashboard_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    print(f"DEBUG DASHBOARD ADMIN - ROL EN SESION: '{rol}'")

    if rol != 'admin':
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    # 🔹 Totales
    cursor.execute("SELECT COUNT(*) FROM alumnos")
    total_alumnos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM docente")
    total_docentes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM curso")
    total_cursos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM asistencia")
    total_asistencia = cursor.fetchone()[0]

    # 🔹 Últimas asistencias
    cursor.execute("""
        SELECT TOP 5 a.fecha, al.nombre, c.nombre_curso, a.estado
        FROM asistencia a
        JOIN inscripcion i ON a.id_inscripcion = i.id_inscripcion
        JOIN alumnos al ON i.id_alumno = al.id_alumno
        JOIN curso c ON i.id_curso = c.id_curso
        ORDER BY a.fecha DESC
    """)
    ultimas_asistencias = cursor.fetchall()

    return render(request, 'admin_dashboard.html', {
        'total_alumnos': total_alumnos,
        'total_docentes': total_docentes,
        'total_cursos': total_cursos,
        'total_asistencia': total_asistencia,
        'ultimas_asistencias': ultimas_asistencias
    })


# =========================
# CRUD ALUMNOS
# =========================

def get_connection():
    return pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=localhost;'
        'DATABASE=proyectoinformatico;'
        'Trusted_Connection=yes;'
    )


# 🔹 LISTAR
def alumnos_list(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM alumnos")
    alumnos = cursor.fetchall()

    return render(request, 'alumnos_list.html', {'alumnos': alumnos})


# 🔹 CREAR
def alumnos_create(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    if request.method == 'POST':
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO alumnos (rut_numero, dv, nombre, apellido_paterno, apellido_materno, fecha_nacimiento, genero,
            nacionalidad, calle, numero, comuna, region, email, fono)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.POST['rut_numero'],
            request.POST['dv'],
            request.POST['nombre'],
            request.POST['apellido_paterno'],
            request.POST['apellido_materno'],
            request.POST['fecha_nacimiento'],
            request.POST['genero'],
            request.POST['nacionalidad'],
            request.POST['calle'],
            request.POST['numero'],
            request.POST['comuna'],
            request.POST['region'],
            request.POST['email'],
            request.POST['fono'],
        ))

        conn.commit()
        return redirect('alumnos_list')

    return render(request, 'alumnos_form.html')


# 🔹 EDITAR
def alumnos_edit(request, id):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        cursor.execute("""
            UPDATE alumnos SET
                rut_numero=?, dv=?, nombre=?, apellido_paterno=?, apellido_materno=?, fecha_nacimiento=?,
                genero=?, nacionalidad=?, calle=?, numero=?, comuna=?, region=?,
                email=?, fono=?
            WHERE id_alumno=?
        """, (
            request.POST['rut_numero'],
            request.POST['dv'],
            request.POST['nombre'],
            request.POST['apellido_paterno'],
            request.POST['apellido_materno'],
            request.POST['fecha_nacimiento'],
            request.POST['genero'],
            request.POST['nacionalidad'],
            request.POST['calle'],
            request.POST['numero'],
            request.POST['comuna'],
            request.POST['region'],
            request.POST['email'],
            request.POST['fono'],
            id
        ))

        conn.commit()
        return redirect('alumnos_list')

    cursor.execute("SELECT * FROM alumnos WHERE id_alumno=?", (id,))
    alumno = cursor.fetchone()

    return render(request, 'alumnos_form.html', {'alumno': alumno})


# 🔹 ELIMINAR
def alumnos_delete(request, id):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM alumnos WHERE id_alumno=?", (id,))
    conn.commit()

    return redirect('alumnos_list')


# =========================
# CRUD DOCENTES
# =========================

# 🔹 LISTAR DOCENTES
def docentes_list(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM docente")
    docentes = cursor.fetchall()

    return render(request, 'docentes_list.html', {'docentes': docentes})


# 🔹 CREAR DOCENTE
def docentes_create(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    if request.method == 'POST':
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO docente (rut, nombre, paterno, materno, email, usuario, password)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            request.POST['rut'],
            request.POST['nombre'],
            request.POST['paterno'],
            request.POST['materno'],
            request.POST['email'],
            request.POST['usuario'],
            request.POST['password'],
        ))

        conn.commit()
        return redirect('docentes_list')

    return render(request, 'docentes_form.html')


# 🔹 EDITAR DOCENTE
def docentes_edit(request, id):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        cursor.execute("""
            UPDATE docente SET
                rut=?, nombre=?, paterno=?, materno=?,
                email=?, usuario=?, password=?
            WHERE id_docente=?
        """, (
            request.POST['rut'],
            request.POST['nombre'],
            request.POST['paterno'],
            request.POST['materno'],
            request.POST['email'],
            request.POST['usuario'],
            request.POST['password'],
            id
        ))

        conn.commit()
        return redirect('docentes_list')

    cursor.execute("SELECT * FROM docente WHERE id_docente=?", (id,))
    docente = cursor.fetchone()

    return render(request, 'docentes_form.html', {'docente': docente})


# 🔹 ELIMINAR DOCENTE
def docentes_delete(request, id):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM docente WHERE id_docente=?", (id,))
    conn.commit()

    return redirect('docentes_list')


# =========================
# CRUD CURSOS
# =========================

# 🔹 LISTAR CURSOS
def cursos_list(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.id_curso, c.nombre_curso, c.año_academico, d.nombre
        FROM curso c
        LEFT JOIN docente d ON c.id_docente = d.id_docente
    """)
    cursos = cursor.fetchall()

    return render(request, 'cursos_list.html', {'cursos': cursos})


# 🔹 CREAR CURSO
def cursos_create(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    # obtener docentes para el select
    cursor.execute("SELECT id_docente, nombre FROM docente")
    docentes = cursor.fetchall()

    if request.method == 'POST':
        cursor.execute("""
            INSERT INTO curso (nombre_curso, año_academico, id_docente)
            VALUES (?, ?, ?)
        """, (
            request.POST['nombre_curso'],
            request.POST['año_academico'],
            request.POST['id_docente']
        ))

        conn.commit()
        return redirect('cursos_list')

    return render(request, 'cursos_form.html', {'docentes': docentes})


# 🔹 EDITAR CURSO
def cursos_edit(request, id):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id_docente, nombre FROM docente")
    docentes = cursor.fetchall()

    if request.method == 'POST':
        cursor.execute("""
            UPDATE curso SET
                nombre_curso=?,
                año_academico=?,
                id_docente=?
            WHERE id_curso=?
        """, (
            request.POST['nombre_curso'],
            request.POST['año_academico'],
            request.POST['id_docente'],
            id
        ))

        conn.commit()
        return redirect('cursos_list')

    cursor.execute("SELECT * FROM curso WHERE id_curso=?", (id,))
    curso = cursor.fetchone()

    return render(request, 'cursos_form.html', {
        'curso': curso,
        'docentes': docentes
    })


# 🔹 ELIMINAR CURSO
def cursos_delete(request, id):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM curso WHERE id_curso=?", (id,))
    conn.commit()

    return redirect('cursos_list')


# =========================
# INSCRIPCIÓN ALUMNOS A CURSOS
# =========================

# 🔹 LISTAR INSCRIPCIONES
def inscripciones_list(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT i.id_inscripcion, a.nombre, a.paterno, c.nombre_curso
        FROM inscripcion i
        JOIN alumnos a ON i.id_alumno = a.id_alumno
        JOIN curso c ON i.id_curso = c.id_curso
    """)
    inscripciones = cursor.fetchall()

    return render(request, 'inscripciones_list.html', {'inscripciones': inscripciones})


# 🔹 CREAR INSCRIPCIÓN
def inscripciones_create(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    # cargar alumnos y cursos
    cursor.execute("SELECT id_alumno, nombre FROM alumnos")
    alumnos = cursor.fetchall()

    cursor.execute("SELECT id_curso, nombre_curso FROM curso")
    cursos = cursor.fetchall()

    if request.method == 'POST':
        cursor.execute("""
            INSERT INTO inscripcion (id_alumno, id_curso)
            VALUES (?, ?)
        """, (
            request.POST['id_alumno'],
            request.POST['id_curso']
        ))

        conn.commit()
        return redirect('inscripciones_list')

    return render(request, 'inscripciones_form.html', {
        'alumnos': alumnos,
        'cursos': cursos
    })


# 🔹 ELIMINAR INSCRIPCIÓN
def inscripciones_delete(request, id):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM inscripcion WHERE id_inscripcion=?", (id,))
    conn.commit()

    return redirect('inscripciones_list')


# =========================
# ASISTENCIA
# =========================

# 🔹 LISTAR ASISTENCIA
def asistencia_list(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.id_asistencia, al.nombre, al.apellido_paterno, c.nombre_curso,
               a.fecha, a.estado
        FROM asistencia a
        JOIN inscripcion i ON a.id_inscripcion = i.id_inscripcion
        JOIN alumnos al ON i.id_alumno = al.id_alumno
        JOIN curso c ON i.id_curso = c.id_curso
        ORDER BY a.fecha DESC
    """)

    asistencias = cursor.fetchall()

    return render(request, 'asistencia_list.html', {'asistencias': asistencias})


# 🔹 CREAR ASISTENCIA
def asistencia_create(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    # traer inscripciones (alumno + curso)
    cursor.execute("""
        SELECT i.id_inscripcion, a.nombre, a.apellido_paterno, c.nombre_curso
        FROM inscripcion i
        JOIN alumnos a ON i.id_alumno = a.id_alumno
        JOIN curso c ON i.id_curso = c.id_curso
    """)
    inscripciones = cursor.fetchall()

    if request.method == 'POST':
        cursor.execute("""
            INSERT INTO asistencia (id_inscripcion, fecha, estado)
            VALUES (?, GETDATE(), ?)
        """, (
            request.POST['id_inscripcion'],
            request.POST['estado']
        ))

        conn.commit()
        return redirect('asistencia_list')

    return render(request, 'asistencia_form.html', {
        'inscripciones': inscripciones
    })


# 🔹 ELIMINAR (opcional pero útil)
def asistencia_delete(request, id):
    if not request.session.get('autenticado'):
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM asistencia WHERE id_asistencia=?", (id,))
    conn.commit()

    return redirect('asistencia_list')


# 🔹 INSCRIBIR ALUMNO
def inscribir_alumno_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # alumnos
        cursor.execute("""
            SELECT id_alumno, nombre, apellido_paterno
            FROM alumnos
        """)
        alumnos = cursor.fetchall()

        # cursos
        cursor.execute("""
            SELECT id_curso, nombre_curso
            FROM curso
        """)
        cursos = cursor.fetchall()

        # guardar inscripción
        if request.method == 'POST':
            id_alumno = request.POST['id_alumno']
            id_curso = request.POST['id_curso']

            cursor.execute("""
                INSERT INTO inscripcion (
                    id_alumno,
                    id_curso
                )
                VALUES (?, ?)
            """, (id_alumno, id_curso))

            conn.commit()

            return render(request,
                'inscribir_alumno.html',
                {
                    'mensaje': 'Alumno inscrito correctamente',
                    'alumnos': alumnos,
                    'cursos': cursos
                }
            )

        return render(request,
            'inscribir_alumno.html',
            {
                'alumnos': alumnos,
                'cursos': cursos
            }
        )

    except Exception as e:
        return render(request,
            'inscribir_alumno.html',
            {
                'error': str(e)
            }
        )


# 🔹 CREAR APODERADO
def crear_apoderado_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    if request.method == 'POST':
        rut = request.POST['rut']
        nombre = request.POST['nombre']
        apellido = request.POST['apellido']
        password = request.POST['password']
        parentesco = request.POST['parentesco']
        fono = request.POST['fono']
        email = request.POST['email']

        try:
            print(f"=" * 50)
            print(f"DEBUG CREAR APODERADO - Email: '{email}', RUT: '{rut}'")
            print(f"=" * 50)

            conn = get_connection()
            cursor = conn.cursor()

            # 1. Insertar en tabla apoderado (SIN contraseña)
            print(f"DEBUG: Insertando en tabla apoderado...")
            cursor.execute("""
                INSERT INTO apoderado (
                    rut,
                    nombre,
                    apellido,
                    parentesco,
                    fono,
                    email
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                rut,
                nombre,
                apellido,
                parentesco,
                fono,
                email
            ))
            print(f"DEBUG: Apoderado insertado OK")

            # 2. Insertar en tabla usuarios para login
            nombre_completo = f"{nombre} {apellido}"
            print(f"DEBUG: Insertando en tabla usuarios...")
            print(f"DEBUG:   correo='{email}', password_hash='{password}', nombre='{nombre_completo}', rol='apoderado'")
            cursor.execute("""
                INSERT INTO usuarios (
                    correo,
                    password_hash,
                    nombre,
                    rol
                )
                VALUES (?, ?, ?, 'apoderado')
            """, (
                email,
                password,
                nombre_completo
            ))
            print(f"DEBUG: Usuario insertado OK")

            conn.commit()
            print(f"DEBUG: Commit realizado OK")

            return render(
                request,
                'crear_apoderado.html',
                {
                    'mensaje': 'Apoderado creado correctamente. Usuario de acceso creado.'
                }
            )

        except Exception as e:
            return render(
                request,
                'crear_apoderado.html',
                {
                    'error': str(e)
                }
            )

    return render(request, 'crear_apoderado.html')


# 🔹 ASIGNAR APODERADO
def asignar_apoderado_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # alumnos
        cursor.execute("""
            SELECT id_alumno, nombre, apellido_paterno
            FROM alumnos
        """)
        alumnos = cursor.fetchall()

        # apoderados
        cursor.execute("""
            SELECT id_apoderado, nombre, parentesco
            FROM apoderado
        """)
        apoderados = cursor.fetchall()

        if request.method == 'POST':
            id_alumno = request.POST['id_alumno']
            id_apoderado = request.POST['id_apoderado']

            cursor.execute("""
                INSERT INTO alumno_apoderado (
                    id_alumno,
                    id_apoderado
                )
                VALUES (?, ?)
            """, (
                id_alumno,
                id_apoderado
            ))

            conn.commit()

            return render(
                request,
                'asignar_apoderado.html',
                {
                    'mensaje': 'Apoderado asignado correctamente',
                    'alumnos': alumnos,
                    'apoderados': apoderados
                }
            )

        return render(
            request,
            'asignar_apoderado.html',
            {
                'alumnos': alumnos,
                'apoderados': apoderados
            }
        )

    except Exception as e:
        return render(
            request,
            'asignar_apoderado.html',
            {
                'error': str(e)
            }
        )


# 🔹 DATOS MÉDICOS
def datos_medicos_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # obtener alumnos
        cursor.execute("""
            SELECT id_alumno, nombre, apellido_paterno
            FROM alumnos
        """)
        alumnos = cursor.fetchall()

        if request.method == 'POST':
            id_alumno = request.POST['id_alumno']
            grupo_sangre = request.POST['grupo_sangre']
            alergias = request.POST['alergias']
            enfermedades = request.POST['enfermedades']

            cursor.execute("""
                INSERT INTO datos_medicos (
                    id_alumno,
                    grupo_sangre,
                    alergias,
                    enfermedades
                )
                VALUES (?, ?, ?, ?)
            """, (
                id_alumno,
                grupo_sangre,
                alergias,
                enfermedades
            ))

            conn.commit()

            return render(
                request,
                'datos_medicos.html',
                {
                    'mensaje': 'Datos médicos guardados correctamente',
                    'alumnos': alumnos
                }
            )

        return render(
            request,
            'datos_medicos.html',
            {
                'alumnos': alumnos
            }
        )

    except Exception as e:
        return render(
            request,
            'datos_medicos.html',
            {
                'error': str(e)
            }
        )


# 🔹 DATOS ACADÉMICOS
def datos_academicos_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # obtener alumnos
        cursor.execute("""
            SELECT id_alumno, nombre, apellido_paterno
            FROM alumnos
        """)
        alumnos = cursor.fetchall()

        if request.method == 'POST':
            id_alumno = request.POST['id_alumno']
            colegio_anterior = request.POST['colegio_anterior']
            estado_academico = request.POST['estado_academico']
            motivo_cambio = request.POST['motivo_cambio']

            cursor.execute("""
                INSERT INTO datos_academicos (
                    id_alumno,
                    colegio_anterior,
                    estado_academico,
                    motivo_cambio
                )
                VALUES (?, ?, ?, ?)
            """, (
                id_alumno,
                colegio_anterior,
                estado_academico,
                motivo_cambio
            ))

            conn.commit()

            return render(
                request,
                'datos_academicos.html',
                {
                    'mensaje': 'Datos académicos guardados correctamente',
                    'alumnos': alumnos
                }
            )

        return render(
            request,
            'datos_academicos.html',
            {
                'alumnos': alumnos
            }
        )

    except Exception as e:
        return render(
            request,
            'datos_academicos.html',
            {
                'error': str(e)
            }
        )


# 🔹 REGISTRAR ASISTENCIA
def registrar_asistencia_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # obtener inscripciones
        cursor.execute("""
            SELECT
                i.id_inscripcion,
                a.nombre,
                a.apellido_paterno,
                c.nombre_curso
            FROM inscripcion i
            INNER JOIN alumnos a
                ON i.id_alumno = a.id_alumno
            INNER JOIN curso c
                ON i.id_curso = c.id_curso
        """)
        inscripciones = cursor.fetchall()

        if request.method == 'POST':
            id_inscripcion = request.POST['id_inscripcion']
            fecha = request.POST['fecha']
            estado = request.POST['estado']

            cursor.execute("""
                INSERT INTO asistencia (
                    id_inscripcion,
                    fecha,
                    estado
                )
                VALUES (?, ?, ?)
            """, (
                id_inscripcion,
                fecha,
                estado
            ))

            conn.commit()

            return render(
                request,
                'registrar_asistencia.html',
                {
                    'mensaje': 'Asistencia registrada correctamente',
                    'inscripciones': inscripciones
                }
            )

        return render(
            request,
            'registrar_asistencia.html',
            {
                'inscripciones': inscripciones
            }
        )

    except Exception as e:
        return render(
            request,
            'registrar_asistencia.html',
            {
                'error': str(e)
            }
        )


# =========================
# DASHBOARD DOCENTE
# =========================

def docente_dashboard_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    print(f"DEBUG DASHBOARD DOCENTE - ROL EN SESION: '{rol}'")

    if rol != 'docente':
        return redirect('login')

    id_usuario = request.session.get('id_usuario')

    conn = get_connection()
    cursor = conn.cursor()

    # 🔹 Obtener docente asociado al usuario (por correo)
    cursor.execute("""
        SELECT d.id_docente, d.nombre
        FROM docente d
        JOIN usuarios u ON u.correo = d.email
        WHERE u.id_usuario = ?
    """, (id_usuario,))

    docente = cursor.fetchone()

    if not docente:
        return redirect('login')

    id_docente = docente[0]
    nombre_docente = docente[1]

    # 🔹 Cursos del docente
    cursor.execute("""
        SELECT id_curso, nombre_curso
        FROM curso
        WHERE id_docente = ?
    """, (id_docente,))
    cursos = cursor.fetchall()
    total_cursos = len(cursos)

    # 🔹 Total alumnos únicos por cursos del docente
    cursor.execute("""
        SELECT COUNT(DISTINCT i.id_alumno)
        FROM inscripcion i
        JOIN curso c ON i.id_curso = c.id_curso
        WHERE c.id_docente = ?
    """, (id_docente,))
    total_alumnos = cursor.fetchone()[0] or 0

    # 🔹 Asistencia HOY
    cursor.execute("""
        SELECT COUNT(*), 
               SUM(CASE WHEN a.estado = 'P' THEN 1 ELSE 0 END) as presentes,
               SUM(CASE WHEN a.estado = 'A' THEN 1 ELSE 0 END) as ausentes
        FROM asistencia a
        JOIN inscripcion i ON a.id_inscripcion = i.id_inscripcion
        JOIN curso c ON i.id_curso = c.id_curso
        WHERE c.id_docente = ? AND CAST(a.fecha AS DATE) = CAST(GETDATE() AS DATE)
    """, (id_docente,))
    asistencia_hoy = cursor.fetchone()
    total_asistencias_hoy = asistencia_hoy[0] or 0
    presentes_hoy = asistencia_hoy[1] or 0

    # 🔹 Últimas observaciones recientes (TABLA NO EXISTE - COMENTADO)
    # cursor.execute("""
    #     SELECT TOP 5 o.fecha, al.nombre, al.apellido_paterno, o.observacion, o.tipo
    #     FROM observaciones o
    #     JOIN alumnos al ON o.id_alumno = al.id_alumno
    #     WHERE o.id_docente = ?
    #     ORDER BY o.fecha DESC
    # """, (id_docente,))
    # observaciones = cursor.fetchall()
    # total_observaciones = len(observaciones)
    observaciones = []
    total_observaciones = 0

    # 🔹 Última asistencia registrada por el docente (para tabla)
    cursor.execute("""
        SELECT TOP 5 a.fecha, al.nombre, al.apellido_paterno, c.nombre_curso, a.estado
        FROM asistencia a
        JOIN inscripcion i ON a.id_inscripcion = i.id_inscripcion
        JOIN alumnos al ON i.id_alumno = al.id_alumno
        JOIN curso c ON i.id_curso = c.id_curso
        WHERE c.id_docente = ?
        ORDER BY a.fecha DESC
    """, (id_docente,))
    asistencias = cursor.fetchall()

    return render(request, 'docente_dashboard.html', {
        'nombre_docente': nombre_docente,
        'cursos': cursos,
        'total_cursos': total_cursos,
        'total_alumnos': total_alumnos,
        'total_asistencias_hoy': total_asistencias_hoy,
        'presentes_hoy': presentes_hoy,
        'observaciones': observaciones,
        'total_observaciones': total_observaciones,
        'asistencias': asistencias
    })


# =========================
# DASHBOARD ALUMNO
# =========================

def alumno_dashboard_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    print(f"DEBUG DASHBOARD ALUMNO - ROL EN SESION: '{rol}'")

    if rol != 'alumno':
        return redirect('login')

    id_usuario = request.session.get('id_usuario')

    conn = get_connection()
    cursor = conn.cursor()

    # Obtener alumno asociado al usuario
    cursor.execute("""
        SELECT a.id_alumno, a.nombre, a.apellido_paterno
        FROM alumnos a
        JOIN usuarios u ON u.correo = a.email
        WHERE u.id_usuario = ?
    """, (id_usuario,))

    alumno = cursor.fetchone()

    if not alumno:
        return redirect('login')

    id_alumno = alumno[0]
    nombre_alumno = f"{alumno[1]} {alumno[2]}"

    # Cursos del alumno
    cursor.execute("""
        SELECT c.nombre_curso, d.nombre as docente
        FROM inscripcion i
        JOIN curso c ON i.id_curso = c.id_curso
        JOIN docente d ON c.id_docente = d.id_docente
        WHERE i.id_alumno = ?
    """, (id_alumno,))
    cursos = cursor.fetchall()

    # Asistencia del alumno
    cursor.execute("""
        SELECT TOP 10 a.fecha, c.nombre_curso, a.estado
        FROM asistencia a
        JOIN inscripcion i ON a.id_inscripcion = i.id_inscripcion
        JOIN curso c ON i.id_curso = c.id_curso
        WHERE i.id_alumno = ?
        ORDER BY a.fecha DESC
    """, (id_alumno,))
    asistencias = cursor.fetchall()

    return render(request, 'alumno_dashboard.html', {
        'nombre_alumno': nombre_alumno,
        'cursos': cursos,
        'asistencias': asistencias
    })

def libro_notas_view(request, id_alumno):
    connection = get_connection()
    cursor = connection.cursor()

    # Ejecutar SP
    cursor.execute(
        "EXEC sp_libro_notas ?",
        [id_alumno]
    )

    resultados = cursor.fetchall()

    # Agrupar notas por materia
    libro = {}

    for row in resultados:
        materia = row[0]
        id_nota = row[1]
        nota = row[2]
        fecha = row[3]

        if materia not in libro:
            libro[materia] = []

        libro[materia].append({
            'id_nota': id_nota,
            'nota': nota,
            'fecha': fecha
        })

    # Obtener promedios
    cursor.execute(
        "EXEC sp_promedio_alumno ?",
        [id_alumno]
    )

    promedios_raw = cursor.fetchall()

    promedios = {}

    for row in promedios_raw:
        promedios[row[0]] = row[1]

    connection.close()

    return render(request,
                  'libro_notas.html',
                  {
                      'libro': libro,
                      'promedios': promedios
                  })

def admin_calificaciones_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    if rol != 'admin':
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    # Obtener todos los alumnos
    cursor.execute("""
        SELECT a.id_alumno, a.nombre, a.apellido_paterno, a.apellido_materno
        FROM alumnos a
        ORDER BY a.apellido_paterno, a.nombre
    """)
    alumnos = cursor.fetchall()

    # Obtener todas las materias
    cursor.execute("""
        SELECT id_materia, nombre
        FROM materias
        ORDER BY nombre
    """)
    materias = cursor.fetchall()

    selected_alumno = None
    libro = {}
    promedios = {}

    # Manejar selección de alumno
    if request.method == 'GET' and 'id_alumno' in request.GET:
        selected_alumno = request.GET.get('id_alumno')

        # Obtener notas del alumno
        cursor.execute(
            "EXEC sp_libro_notas ?",
            [selected_alumno]
        )
        resultados = cursor.fetchall()

        # Obtener promedios
        cursor.execute(
            "EXEC sp_promedio_alumno ?",
            [selected_alumno]
        )
        promedios_raw = cursor.fetchall()

        # Crear diccionario de promedios
        promedios_dict = {}
        for row in promedios_raw:
            promedios_dict[row[0]] = row[1]

        # Agrupar notas por materia con promedio incluido
        for row in resultados:
            materia = row[0]
            id_nota = row[1]
            nota = row[2]
            fecha = row[3]

            if materia not in libro:
                libro[materia] = {
                    'notas': [],
                    'promedio': promedios_dict.get(materia, 0)
                }

            libro[materia]['notas'].append({
                'id_nota': id_nota,
                'nota': nota,
                'fecha': fecha
            })

    # Manejar agregado de calificación
    if request.method == 'POST':
        id_materia = request.POST.get('materia')
        nota = request.POST.get('nota')
        selected_alumno = request.POST.get('id_alumno')

        if id_materia and nota and selected_alumno:
            # Insertar nueva calificación
            cursor.execute("""
                INSERT INTO notas (id_alumno, id_materia, nota, fecha)
                VALUES (?, ?, ?, GETDATE())
            """, (selected_alumno, id_materia, nota))
            conn.commit()

            # Recargar notas del alumno
            cursor.execute(
                "EXEC sp_libro_notas ?",
                [selected_alumno]
            )
            resultados = cursor.fetchall()

            # Recargar promedios
            cursor.execute(
                "EXEC sp_promedio_alumno ?",
                [selected_alumno]
            )
            promedios_raw = cursor.fetchall()

            # Crear diccionario de promedios
            promedios_dict = {}
            for row in promedios_raw:
                promedios_dict[row[0]] = row[1]

            # Agrupar notas por materia con promedio incluido
            libro = {}
            for row in resultados:
                materia_row = row[0]
                id_nota = row[1]
                nota_row = row[2]
                fecha = row[3]

                if materia_row not in libro:
                    libro[materia_row] = {
                        'notas': [],
                        'promedio': promedios_dict.get(materia_row, 0)
                    }

                libro[materia_row]['notas'].append({
                    'id_nota': id_nota,
                    'nota': nota_row,
                    'fecha': fecha
                })

    conn.close()

    return render(request, 'admin_calificaciones.html', {
        'alumnos': alumnos,
        'selected_alumno': selected_alumno,
        'libro': libro,
        'materias': materias
    })


# =========================
# ADMIN ASISTENCIA
# =========================

def admin_asistencia_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    if rol != 'admin':
        return redirect('login')

    with connection.cursor() as cursor:
        # CURSOS
        cursor.execute("""
            SELECT id_curso, nombre_curso
            FROM curso
        """)
        cursos = cursor.fetchall()

        id_curso = request.GET.get('id_curso')
        fecha = request.GET.get('fecha') or str(date.today())

        alumnos = []
        nombre_curso = ""
        profesor = ""
        asistencias = []

        if id_curso:
            # INFO CURSO + PROFESOR
            cursor.execute("""
                SELECT
                    c.nombre_curso,
                    d.nombre
                FROM curso c
                LEFT JOIN docente d
                    ON c.id_docente = d.id_docente
                WHERE c.id_curso = %s
            """, [id_curso])

            curso_info = cursor.fetchone()

            if curso_info:
                nombre_curso = curso_info[0]
                profesor = curso_info[1]

            # ALUMNOS
            cursor.execute("""
                SELECT
                    i.id_inscripcion,
                    a.nombre,
                    a.apellido_paterno,
                    a.apellido_materno
                FROM inscripcion i
                INNER JOIN alumnos a
                    ON i.id_alumno = a.id_alumno
                WHERE i.id_curso = %s
                ORDER BY a.apellido_paterno
            """, [id_curso])

            alumnos = cursor.fetchall()

            # ASISTENCIAS EXISTENTES
            cursor.execute("""
                SELECT
                    asi.id_asistencia,
                    a.nombre,
                    a.apellido_paterno,
                    a.apellido_materno,
                    asi.estado,
                    asi.fecha
                FROM asistencia asi
                INNER JOIN inscripcion i ON asi.id_inscripcion = i.id_inscripcion
                INNER JOIN alumnos a ON i.id_alumno = a.id_alumno
                WHERE i.id_curso = %s
                AND asi.fecha = %s
                ORDER BY a.apellido_paterno
            """, [id_curso, fecha])

            rows = cursor.fetchall()

            for row in rows:
                asistencias.append({
                    "id_asistencia": row[0],
                    "nombre": row[1],
                    "apellido_paterno": row[2],
                    "apellido_materno": row[3],
                    "estado": row[4],
                    "fecha": row[5],
                    "curso": nombre_curso,
                    "profesor": profesor
                })

        # GUARDAR ASISTENCIA
        if request.method == "POST":
            fecha = request.POST.get("fecha")

            for alumno in alumnos:
                id_inscripcion = alumno[0]
                estado = request.POST.get(f'estado_{id_inscripcion}')

                # VERIFICAR SI YA EXISTE
                cursor.execute("""
                    SELECT id_asistencia
                    FROM asistencia
                    WHERE id_inscripcion = %s
                    AND fecha = %s
                """, [id_inscripcion, fecha])

                existe = cursor.fetchone()

                if existe:
                    # UPDATE
                    cursor.execute("""
                        UPDATE asistencia
                        SET estado = %s
                        WHERE id_asistencia = %s
                    """, [estado, existe[0]])
                else:
                    # INSERT
                    cursor.execute("""
                        INSERT INTO asistencia
                        (id_inscripcion, fecha, estado)
                        VALUES (%s, %s, %s)
                    """, [id_inscripcion, fecha, estado])

            # RECARGAR ASISTENCIAS
            cursor.execute("""
                SELECT
                    asi.id_asistencia,
                    a.nombre,
                    a.apellido_paterno,
                    a.apellido_materno,
                    asi.estado,
                    asi.fecha
                FROM asistencia asi
                INNER JOIN inscripcion i ON asi.id_inscripcion = i.id_inscripcion
                INNER JOIN alumnos a ON i.id_alumno = a.id_alumno
                WHERE i.id_curso = %s
                AND asi.fecha = %s
                ORDER BY a.apellido_paterno
            """, [id_curso, fecha])

            rows = cursor.fetchall()

            asistencias = []
            for row in rows:
                asistencias.append({
                    "id_asistencia": row[0],
                    "nombre": row[1],
                    "apellido_paterno": row[2],
                    "apellido_materno": row[3],
                    "estado": row[4],
                    "fecha": row[5],
                    "curso": nombre_curso,
                    "profesor": profesor
                })

    return render(request, 'admin_asistencia.html', {
        'cursos': cursos,
        'alumnos': alumnos,
        'nombre_curso': nombre_curso,
        'profesor': profesor,
        'fecha_actual': date.today(),
        'fecha': fecha,
        'asistencias': asistencias
    })


# =========================
# DASHBOARD APODERADO
# =========================

def apoderado_dashboard_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    print(f"DEBUG DASHBOARD APODERADO - ROL EN SESION: '{rol}'")

    if rol != 'apoderado':
        return redirect('login')

    id_usuario = request.session.get('id_usuario')

    conn = get_connection()
    cursor = conn.cursor()

    # Obtener apoderado asociado al usuario
    cursor.execute("""
        SELECT id_apoderado, nombre
        FROM apoderado
        WHERE email = (SELECT correo FROM usuarios WHERE id_usuario = ?)
    """, (id_usuario,))

    apoderado = cursor.fetchone()

    if not apoderado:
        return redirect('login')

    id_apoderado = apoderado[0]
    nombre_apoderado = apoderado[1]

    # Alumnos a cargo del apoderado
    cursor.execute("""
        SELECT a.id_alumno, a.nombre, a.apellido_paterno, a.apellido_materno, c.nombre_curso
        FROM alumno_apoderado aa
        JOIN alumnos a ON aa.id_alumno = a.id_alumno
        LEFT JOIN inscripcion i ON a.id_alumno = i.id_alumno
        LEFT JOIN curso c ON i.id_curso = c.id_curso
        WHERE aa.id_apoderado = ?
    """, (id_apoderado,))
    alumnos = cursor.fetchall()

    return render(request, 'apoderado_dashboard.html', {
        'nombre_apoderado': nombre_apoderado,
        'alumnos': alumnos
    })


def apoderado_hijos_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    if rol != 'apoderado':
        return redirect('login')

    id_usuario = request.session.get('id_usuario')
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id_apoderado, nombre, apellido
        FROM apoderado
        WHERE email = (SELECT correo FROM usuarios WHERE id_usuario = ?)
    """, (id_usuario,))
    apoderado = cursor.fetchone()

    if not apoderado:
        return redirect('login')

    id_apoderado = apoderado[0]
    nombre_apoderado = f"{apoderado[1]} {apoderado[2]}"

    cursor.execute("""
        SELECT a.id_alumno, a.nombre, a.apellido_paterno, a.apellido_materno,
               a.fecha_nacimiento, a.genero, a.email, a.fono,
               c.nombre_curso, c.nivel
        FROM alumno_apoderado aa
        JOIN alumnos a ON aa.id_alumno = a.id_alumno
        LEFT JOIN inscripcion i ON a.id_alumno = i.id_alumno
        LEFT JOIN curso c ON i.id_curso = c.id_curso
        WHERE aa.id_apoderado = ?
    """, (id_apoderado,))
    hijos = cursor.fetchall()

    return render(request, 'apoderado_hijos.html', {
        'nombre_apoderado': nombre_apoderado,
        'hijos': hijos
    })


def apoderado_asistencia_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    if rol != 'apoderado':
        return redirect('login')

    id_usuario = request.session.get('id_usuario')
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id_apoderado, nombre, apellido
        FROM apoderado
        WHERE email = (SELECT correo FROM usuarios WHERE id_usuario = ?)
    """, (id_usuario,))
    apoderado = cursor.fetchone()

    if not apoderado:
        return redirect('login')

    id_apoderado = apoderado[0]
    nombre_apoderado = f"{apoderado[1]} {apoderado[2]}"

    cursor.execute("""
        SELECT a.nombre, a.apellido_paterno, a.apellido_materno,
               asis.fecha, asis.estado, c.nombre_curso
        FROM alumno_apoderado aa
        JOIN alumnos a ON aa.id_alumno = a.id_alumno
        LEFT JOIN asistencia asis ON a.id_alumno = asis.id_alumno
        LEFT JOIN curso c ON asis.id_curso = c.id_curso
        WHERE aa.id_apoderado = ?
        ORDER BY asis.fecha DESC
    """, (id_apoderado,))
    asistencias = cursor.fetchall()

    return render(request, 'apoderado_asistencia.html', {
        'nombre_apoderado': nombre_apoderado,
        'asistencias': asistencias
    })


def apoderado_notas_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    if rol != 'apoderado':
        return redirect('login')

    id_usuario = request.session.get('id_usuario')
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id_apoderado, nombre, apellido
        FROM apoderado
        WHERE email = (SELECT correo FROM usuarios WHERE id_usuario = ?)
    """, (id_usuario,))
    apoderado = cursor.fetchone()

    if not apoderado:
        return redirect('login')

    id_apoderado = apoderado[0]
    nombre_apoderado = f"{apoderado[1]} {apoderado[2]}"

    cursor.execute("""
        SELECT a.nombre, a.apellido_paterno, a.apellido_materno,
               n.nota, n.fecha_evaluacion, c.nombre_curso, asig.nombre_asignatura
        FROM alumno_apoderado aa
        JOIN alumnos a ON aa.id_alumno = a.id_alumno
        LEFT JOIN notas n ON a.id_alumno = n.id_alumno
        LEFT JOIN curso c ON n.id_curso = c.id_curso
        LEFT JOIN asignaturas asig ON n.id_asignatura = asig.id_asignatura
        WHERE aa.id_apoderado = ?
        ORDER BY n.fecha_evaluacion DESC
    """, (id_apoderado,))
    notas = cursor.fetchall()

    return render(request, 'apoderado_notas.html', {
        'nombre_apoderado': nombre_apoderado,
        'notas': notas
    })


def apoderado_medico_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    if rol != 'apoderado':
        return redirect('login')

    id_usuario = request.session.get('id_usuario')
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id_apoderado, nombre, apellido
        FROM apoderado
        WHERE email = (SELECT correo FROM usuarios WHERE id_usuario = ?)
    """, (id_usuario,))
    apoderado = cursor.fetchone()

    if not apoderado:
        return redirect('login')

    id_apoderado = apoderado[0]
    nombre_apoderado = f"{apoderado[1]} {apoderado[2]}"

    cursor.execute("""
        SELECT a.nombre, a.apellido_paterno, a.apellido_materno,
               dm.alergias, dm.enfermedades_cronicas, dm.medicamentos,
               dm.contacto_emergencia, dm.fono_emergencia
        FROM alumno_apoderado aa
        JOIN alumnos a ON aa.id_alumno = a.id_alumno
        LEFT JOIN datos_medicos dm ON a.id_alumno = dm.id_alumno
        WHERE aa.id_apoderado = ?
    """, (id_apoderado,))
    datos_medicos = cursor.fetchall()

    return render(request, 'apoderado_medico.html', {
        'nombre_apoderado': nombre_apoderado,
        'datos_medicos': datos_medicos
    })


def apoderado_observaciones_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    if rol != 'apoderado':
        return redirect('login')

    id_usuario = request.session.get('id_usuario')
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id_apoderado, nombre, apellido
        FROM apoderado
        WHERE email = (SELECT correo FROM usuarios WHERE id_usuario = ?)
    """, (id_usuario,))
    apoderado = cursor.fetchone()

    if not apoderado:
        return redirect('login')

    id_apoderado = apoderado[0]
    nombre_apoderado = f"{apoderado[1]} {apoderado[2]}"

    cursor.execute("""
        SELECT a.nombre, a.apellido_paterno, a.apellido_materno,
               o.fecha, o.observacion, o.tipo, d.nombre as docente
        FROM alumno_apoderado aa
        JOIN alumnos a ON aa.id_alumno = a.id_alumno
        LEFT JOIN observaciones o ON a.id_alumno = o.id_alumno
        LEFT JOIN docente d ON o.id_docente = d.id_docente
        WHERE aa.id_apoderado = ?
        ORDER BY o.fecha DESC
    """, (id_apoderado,))
    observaciones = cursor.fetchall()

    return render(request, 'apoderado_observaciones.html', {
        'nombre_apoderado': nombre_apoderado,
        'observaciones': observaciones
    })


# =========================
# TOMA DE DATOS (ADMIN)
# =========================

def toma_datos_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    if request.session.get('rol') != 'admin':
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    # 🔹 Estadísticas para la toma de datos
    cursor.execute("SELECT COUNT(*) FROM alumnos")
    total_alumnos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM docente")
    total_docentes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM curso")
    total_cursos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM inscripcion")
    total_inscripciones = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM asistencia")
    total_asistencias = cursor.fetchone()[0]

    return render(request, 'toma_datos.html', {
        'total_alumnos': total_alumnos,
        'total_docentes': total_docentes,
        'total_cursos': total_cursos,
        'total_inscripciones': total_inscripciones,
        'total_asistencias': total_asistencias
    })


# =========================
# AUDITORIA (ADMIN)
# =========================

def auditoria_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    if request.session.get('rol') != 'admin':
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    # 🔹 Obtener logs de auditoría desde la tabla de logs o intentos_login
    try:
        # Intentar usar la tabla logs (nueva estructura con SP)
        cursor.execute("""
            SELECT TOP 50 l.fecha, u.correo, l.accion, l.ip
            FROM logs l
            LEFT JOIN usuarios u ON l.id_usuario = u.id_usuario
            ORDER BY l.fecha DESC
        """)
        logs = cursor.fetchall()
    except:
        # Fallback a intentos_login (estructura antigua)
        cursor.execute("""
            SELECT TOP 50 fecha_intento, correo, 
                CASE WHEN exito = 1 THEN 'Inicio sesión exitoso' ELSE 'Intento fallido' END,
                ip
            FROM intentos_login
            ORDER BY fecha_intento DESC
        """)
        logs = cursor.fetchall()

    return render(request, 'auditoria.html', {
        'logs': logs
    })


# 🔹 CREAR ALUMNO (VISTA ESPECÍFICA)
def crear_alumno_view(request):
    if request.method == 'POST':
        try:
            # DEBUG: Ver qué llega del formulario
            print("=" * 50)
            print("DEBUG request.POST:", dict(request.POST))
            print("=" * 50)

            # Obtener RUT número y DV directamente del formulario
            rut_numero = request.POST.get('rut_numero', '').strip()
            dv = request.POST.get('dv', '').strip().upper()

            print(f"DEBUG rut_numero: '{rut_numero}', dv: '{dv}'")

            # Validación: RUT número no vacío y solo dígitos
            if not rut_numero:
                return render(request, 'alumnos_form.html', {
                    'error': 'El campo RUT número es obligatorio'
                })

            if not rut_numero.isdigit():
                return render(request, 'alumnos_form.html', {
                    'error': 'El RUT solo puede contener números'
                })

            # Validación: RUT no puede superar 8 dígitos
            if len(rut_numero) > 8:
                return render(request, 'alumnos_form.html', {
                    'error': 'El RUT no puede superar 8 dígitos'
                })

            # Validación: DV no vacío
            if not dv:
                return render(request, 'alumnos_form.html', {
                    'error': 'El dígito verificador (DV) es obligatorio'
                })

            # Validación: Usar RutValidator para validar DV
            validator = RutValidator()
            rut_completo = rut_numero + '-' + dv

            if not validator.validar(rut_completo):
                dv_esperado = validator.calcular_dv(rut_numero)
                return render(request, 'alumnos_form.html', {
                    'error': f'El dígito verificador es incorrecto. DV esperado: {dv_esperado}, DV ingresado: {dv}'
                })

            conn = get_connection()
            cursor = conn.cursor()

            # Obtener datos con .get() para evitar errores si vienen vacíos
            nombre = request.POST.get('nombre', '').strip()
            ap_paterno = request.POST.get('apellido_paterno', '').strip()
            ap_materno = request.POST.get('apellido_materno', '').strip()
            fecha = request.POST.get('fecha_nacimiento', '')
            genero = request.POST.get('genero', 'M')
            nacionalidad = request.POST.get('nacionalidad', 'Chilena')
            calle = request.POST.get('calle', '').strip()
            numero = request.POST.get('numero', '').strip()
            comuna = request.POST.get('comuna', 'Santiago')
            region = request.POST.get('region', 'RM')
            email = request.POST.get('email', '').strip()
            fono = request.POST.get('fono', '').strip()

            print(f"DEBUG datos: rut={rut_numero}, dv={dv}, nombre={nombre}")

            cursor.execute("""
                EXEC sp_insertar_alumno ?,?,?,?,?,?,?,?,?,?,?,?,?,?
            """, (
                rut_numero, dv, nombre, ap_paterno, ap_materno,
                fecha, genero, nacionalidad,
                calle, numero, comuna, region, email, fono
            ))

            conn.commit()

            return render(request, 'alumnos_form.html', {
                'mensaje': 'Alumno guardado correctamente'
            })

        except Exception as e:
            return render(request, 'alumnos_form.html', {
                'error': str(e)
            })

# =========================
# VISTAS ESPECÍFICAS DEL DOCENTE
# =========================

def docente_pasar_asistencia_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    if rol != 'docente':
        return redirect('login')

    id_usuario = request.session.get('id_usuario')

    conn = get_connection()
    cursor = conn.cursor()

    # Obtener docente
    cursor.execute("""
        SELECT d.id_docente, d.nombre
        FROM docente d
        JOIN usuarios u ON u.correo = d.email
        WHERE u.id_usuario = ?
    """, (id_usuario,))
    docente = cursor.fetchone()

    if not docente:
        return redirect('login')

    id_docente = docente[0]
    nombre_docente = docente[1]

    # Obtener cursos del docente
    cursor.execute("""
        SELECT id_curso, nombre_curso
        FROM curso
        WHERE id_docente = ?
    """, (id_docente,))
    cursos = cursor.fetchall()

    if request.method == 'POST':
        id_curso = request.POST.get('id_curso')
        fecha = request.POST.get('fecha')

        # Obtener alumnos inscritos en el curso
        cursor.execute("""
            SELECT i.id_inscripcion, a.nombre, a.apellido_paterno
            FROM inscripcion i
            JOIN alumnos a ON i.id_alumno = a.id_alumno
            WHERE i.id_curso = ?
        """, (id_curso,))
        alumnos = cursor.fetchall()

        # Procesar asistencia
        for alumno in alumnos:
            id_inscripcion = alumno[0]
            estado = request.POST.get(f'estado_{id_inscripcion}', 'A')

            # Verificar si ya existe asistencia para esa fecha
            cursor.execute("""
                SELECT id_asistencia FROM asistencia
                WHERE id_inscripcion = ? AND CAST(fecha AS DATE) = ?
            """, (id_inscripcion, fecha))

            existing = cursor.fetchone()

            if existing:
                # Actualizar
                cursor.execute("""
                    UPDATE asistencia SET estado = ?
                    WHERE id_inscripcion = ? AND CAST(fecha AS DATE) = ?
                """, (estado, id_inscripcion, fecha))
            else:
                # Insertar
                cursor.execute("""
                    INSERT INTO asistencia (id_inscripcion, fecha, estado)
                    VALUES (?, ?, ?)
                """, (id_inscripcion, fecha, estado))

        conn.commit()
        return redirect('docente_pasar_asistencia')

    # GET request - mostrar formulario
    return render(request, 'docente_pasar_asistencia.html', {
        'nombre_docente': nombre_docente,
        'cursos': cursos,
        'fecha_hoy': datetime.now().strftime('%Y-%m-%d')
    })

def docente_ver_alumnos_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    if rol != 'docente':
        return redirect('login')

    id_usuario = request.session.get('id_usuario')

    conn = get_connection()
    cursor = conn.cursor()

    # Obtener docente
    cursor.execute("""
        SELECT d.id_docente, d.nombre
        FROM docente d
        JOIN usuarios u ON u.correo = d.email
        WHERE u.id_usuario = ?
    """, (id_usuario,))
    docente = cursor.fetchone()

    if not docente:
        return redirect('login')

    id_docente = docente[0]
    nombre_docente = docente[1]

    # Obtener alumnos de los cursos del docente
    cursor.execute("""
        SELECT DISTINCT a.id_alumno, a.nombre, a.apellido_paterno, a.email, c.nombre_curso
        FROM alumnos a
        JOIN inscripcion i ON a.id_alumno = i.id_alumno
        JOIN curso c ON i.id_curso = c.id_curso
        WHERE c.id_docente = ?
        ORDER BY a.apellido_paterno, a.nombre
    """, (id_docente,))
    alumnos = cursor.fetchall()

    return render(request, 'docente_ver_alumnos.html', {
        'nombre_docente': nombre_docente,
        'alumnos': alumnos
    })

def docente_ver_cursos_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    if rol != 'docente':
        return redirect('login')

    id_usuario = request.session.get('id_usuario')

    conn = get_connection()
    cursor = conn.cursor()

    # Obtener docente
    cursor.execute("""
        SELECT d.id_docente, d.nombre
        FROM docente d
        JOIN usuarios u ON u.correo = d.email
        WHERE u.id_usuario = ?
    """, (id_usuario,))
    docente = cursor.fetchone()

    if not docente:
        return redirect('login')

    id_docente = docente[0]
    nombre_docente = docente[1]

    # Obtener cursos del docente con conteo de alumnos
    cursor.execute("""
        SELECT c.id_curso, c.nombre_curso, c.año_academico,
               COUNT(DISTINCT i.id_alumno) as num_alumnos
        FROM curso c
        LEFT JOIN inscripcion i ON c.id_curso = i.id_curso
        WHERE c.id_docente = ?
        GROUP BY c.id_curso, c.nombre_curso, c.año_academico
    """, (id_docente,))
    cursos = cursor.fetchall()

    return render(request, 'docente_ver_cursos.html', {
        'nombre_docente': nombre_docente,
        'cursos': cursos
    })

def docente_ver_asistencia_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    if rol != 'docente':
        return redirect('login')

    id_usuario = request.session.get('id_usuario')

    conn = get_connection()
    cursor = conn.cursor()

    # Obtener docente
    cursor.execute("""
        SELECT d.id_docente, d.nombre
        FROM docente d
        JOIN usuarios u ON u.correo = d.email
        WHERE u.id_usuario = ?
    """, (id_usuario,))
    docente = cursor.fetchone()

    if not docente:
        return redirect('login')

    id_docente = docente[0]
    nombre_docente = docente[1]

    # Obtener cursos del docente
    cursor.execute("""
        SELECT id_curso, nombre_curso
        FROM curso
        WHERE id_docente = ?
    """, (id_docente,))
    cursos = cursor.fetchall()

    # Obtener asistencia filtrada por curso y fecha si se proporcionan
    id_curso = request.GET.get('id_curso')
    fecha = request.GET.get('fecha')

    query = """
        SELECT a.fecha, al.nombre, al.apellido_paterno, c.nombre_curso, a.estado
        FROM asistencia a
        JOIN inscripcion i ON a.id_inscripcion = i.id_inscripcion
        JOIN alumnos al ON i.id_alumno = al.id_alumno
        JOIN curso c ON i.id_curso = c.id_curso
        WHERE c.id_docente = ?
    """
    params = [id_docente]

    if id_curso:
        query += " AND c.id_curso = ?"
        params.append(id_curso)

    if fecha:
        query += " AND CAST(a.fecha AS DATE) = ?"
        params.append(fecha)

    query += " ORDER BY a.fecha DESC, al.apellido_paterno, al.nombre"

    cursor.execute(query, params)
    asistencias = cursor.fetchall()

    return render(request, 'docente_ver_asistencia.html', {
        'nombre_docente': nombre_docente,
        'cursos': cursos,
        'asistencias': asistencias,
        'selected_curso': id_curso,
        'selected_fecha': fecha
    })

def gestion_cursos_view(request):
    if not request.session.get('autenticado'):
        return redirect('login')

    rol = request.session.get('rol', '').lower()
    if rol != 'admin':
        return redirect('login')

    conn = get_connection()
    cursor = conn.cursor()

    # Obtener todos los cursos ordenados por nombre (1° Básico a 8° Básico)
    cursor.execute("""
        SELECT c.id_curso, c.nombre_curso, c.año_academico,
               COUNT(DISTINCT i.id_alumno) as num_alumnos,
               d.nombre as nombre_docente
        FROM curso c
        LEFT JOIN inscripcion i ON c.id_curso = i.id_curso
        LEFT JOIN docente d ON c.id_docente = d.id_docente
        GROUP BY c.id_curso, c.nombre_curso, c.año_academico, d.nombre
        ORDER BY c.nombre_curso
    """)
    cursos = cursor.fetchall()

    return render(request, 'gestion_cursos.html', {
        'cursos': cursos
    })