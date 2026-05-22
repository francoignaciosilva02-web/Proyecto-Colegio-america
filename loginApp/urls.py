from django.urls import path
from .views import *

urlpatterns = [
    # LOGIN
    path('', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('token/', token_view, name='token'),

    # DASHBOARD
    path('admin/dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('docente/dashboard/', docente_dashboard_view, name='docente_dashboard'),
    path('alumno/dashboard/', alumno_dashboard_view, name='alumno_dashboard'),
    path('apoderado/dashboard/', apoderado_dashboard_view, name='apoderado_dashboard'),
    path('apoderado/hijos/', apoderado_hijos_view, name='apoderado_hijos'),
    path('apoderado/asistencia/', apoderado_asistencia_view, name='apoderado_asistencia'),
    path('apoderado/notas/', apoderado_notas_view, name='apoderado_notas'),
    path('apoderado/medico/', apoderado_medico_view, name='apoderado_medico'),
    path('apoderado/observaciones/', apoderado_observaciones_view, name='apoderado_observaciones'),

    # CRUD ALUMNOS
    path('alumnos/', alumnos_list, name='alumnos_list'),
    path('alumnos/crear/', alumnos_create, name='alumnos_create'),
    path('alumnos/editar/<int:id>/', alumnos_edit, name='alumnos_edit'),
    path('alumnos/eliminar/<int:id>/', alumnos_delete, name='alumnos_delete'),

    # CRUD DOCENTES
    path('docentes/', docentes_list, name='docentes_list'),
    path('docentes/crear/', docentes_create, name='docentes_create'),
    path('docentes/editar/<int:id>/', docentes_edit, name='docentes_edit'),
    path('docentes/eliminar/<int:id>/', docentes_delete, name='docentes_delete'),

    # CRUD CURSOS
    path('cursos/', cursos_list, name='cursos_list'),
    path('cursos/crear/', cursos_create, name='cursos_create'),
    path('cursos/editar/<int:id>/', cursos_edit, name='cursos_edit'),
    path('cursos/eliminar/<int:id>/', cursos_delete, name='cursos_delete'),
    path('cursos/detalle/<int:id_curso>/', curso_detalle_view, name='curso_detalle'),
    path('gestion-cursos/', gestion_cursos_view, name='gestion_cursos'),

    # INSCRIPCIONES
    path('inscripciones/', inscripciones_list, name='inscripciones_list'),
    path('inscripciones/crear/', inscripciones_create, name='inscripciones_create'),
    path('inscripciones/eliminar/<int:id>/', inscripciones_delete, name='inscripciones_delete'),
    path('inscribir-alumno/', inscribir_alumno_view, name='inscribir_alumno'),

    # ASISTENCIA
    path('asistencia/', asistencia_list, name='asistencia_list'),
    path('asistencia/crear/', asistencia_create, name='asistencia_create'),
    path('asistencia/eliminar/<int:id>/', asistencia_delete, name='asistencia_delete'),
    path('registrar-asistencia/', registrar_asistencia_view, name='registrar_asistencia'),

    # TOMA DE DATOS (ADMIN)
    path('admin/toma-datos/', toma_datos_view, name='toma_datos'),
    path('admin/auditoria/', auditoria_view, name='auditoria'),

    # CREAR ALUMNO (NUEVO)
    path('crear-alumno/', crear_alumno_view, name='crear_alumno'),

    # APODERADOS
    path('crear-apoderado/', crear_apoderado_view, name='crear_apoderado'),
    path('asignar-apoderado/', asignar_apoderado_view, name='asignar_apoderado'),

    # INFORMACIÓN COMPLEMENTARIA
    path('datos-medicos/', datos_medicos_view, name='datos_medicos'),
    path('datos-academicos/', datos_academicos_view, name='datos_academicos'),

    # VISTAS ESPECÍFICAS DEL DOCENTE
    path('docente/pasar-asistencia/', docente_pasar_asistencia_view, name='docente_pasar_asistencia'),
    path('docente/ver-alumnos/', docente_ver_alumnos_view, name='docente_ver_alumnos'),
    path('docente/ver-cursos/', docente_ver_cursos_view, name='docente_ver_cursos'),
    path('docente/ver-asistencia/', docente_ver_asistencia_view, name='docente_ver_asistencia'),
    path('docente/ver-calificaciones/', docente_ver_calificaciones_view, name='docente_ver_calificaciones'),

    # LIBRO DE NOTAS
    path('libro-notas/<int:id_alumno>/', libro_notas_view, name='libro_notas'),

    # ADMIN CALIFICACIONES
    path('admin/calificaciones/', admin_calificaciones_view, name='admin_calificaciones'),

    # ADMIN ASISTENCIA
    path('admin/asistencia/', admin_asistencia_view, name='admin_asistencia'),
]