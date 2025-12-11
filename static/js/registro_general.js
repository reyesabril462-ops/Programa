document.addEventListener('DOMContentLoaded', function () {
  var rol = document.getElementById('rol');
  var alumnoCampos = document.getElementById('alumno-campos');
  var docenteCampos = document.getElementById('docente-campos');
  var grupo = document.getElementById('grupo');
  var semestre = document.getElementById('semestre');
  var materia = document.getElementById('materia');

  function updateFields() {
    var val = rol ? rol.value : '';
    if (val === 'alumno') {
      if (alumnoCampos) alumnoCampos.style.display = 'block';
      if (docenteCampos) docenteCampos.style.display = 'none';
      if (grupo) grupo.required = true;
      if (semestre) semestre.required = true;
      if (materia) materia.required = false;
    } else if (val === 'docente') {
      if (alumnoCampos) alumnoCampos.style.display = 'none';
      if (docenteCampos) docenteCampos.style.display = 'block';
      if (grupo) grupo.required = false;
      if (semestre) semestre.required = false;
      if (materia) materia.required = true;
    } else {
      if (alumnoCampos) alumnoCampos.style.display = 'none';
      if (docenteCampos) docenteCampos.style.display = 'none';
      if (grupo) grupo.required = false;
      if (semestre) semestre.required = false;
      if (materia) materia.required = false;
    }
  }

  if (rol) {
    rol.addEventListener('change', updateFields);
    // call once to set initial visibility (useful if form re-renders with a selected value)
    updateFields();
  }
});
