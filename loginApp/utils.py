import re
from typing import Optional, Tuple, Union


class RutValidator:
    """Clase para validar y formatear RUTs chilenos."""

    def __init__(self):
        self._cache = {}
        self._max_cache_size = 1000

    @staticmethod
    def limpiar(rut: str) -> str:
        """
        Limpia el RUT removiendo puntos, guiones y espacios.

        Args:
            rut: RUT en cualquier formato

        Returns:
            RUT limpio solo con números y K
        """
        return re.sub(r'[.\-\s]', '', str(rut)).upper()

    @staticmethod
    def formatear(rut: str) -> str:
        """
        Formatea el RUT con puntos y guión.

        Args:
            rut: RUT sin formato

        Returns:
            RUT formateado (ej: 12.345.678-9)
        """
        rut_limpio = RutValidator.limpiar(rut)

        if len(rut_limpio) < 2:
            return rut_limpio

        # Separar número y dígito verificador
        numero = rut_limpio[:-1]
        dv = rut_limpio[-1]

        # Formatear número con puntos
        numero_formateado = ''
        for i, digito in enumerate(reversed(numero)):
            if i > 0 and i % 3 == 0:
                numero_formateado = '.' + numero_formateado
            numero_formateado = digito + numero_formateado

        return f"{numero_formateado}-{dv}"

    @staticmethod
    def calcular_dv(rut_numero: Union[int, str]) -> str:
        """
        Calcula el dígito verificador.

        Args:
            rut_numero: Número del RUT sin DV

        Returns:
            Dígito verificador
        """
        # Asegurar string de 8 dígitos
        rut_str = str(rut_numero).zfill(8)

        # Calcular suma ponderada
        suma = sum(
            int(digito) * (2 + (i % 6))
            for i, digito in enumerate(reversed(rut_str))
        )

        # Obtener dígito verificador
        dv = 11 - (suma % 11)

        if dv == 11:
            return '0'
        elif dv == 10:
            return 'K'
        else:
            return str(dv)

    def validar(self, rut: str) -> bool:
        """
        Valida un RUT completo.

        Args:
            rut: RUT completo con o sin formato

        Returns:
            True si es válido, False en caso contrario
        """
        rut_limpio = self.limpiar(rut)

        # Verificar cache
        if rut_limpio in self._cache:
            return self._cache[rut_limpio]

        # Validación
        resultado = self._validar_sin_cache(rut_limpio)

        # Actualizar cache
        self._actualizar_cache(rut_limpio, resultado)

        return resultado

    def _validar_sin_cache(self, rut_limpio: str) -> bool:
        """Realiza la validación sin usar cache."""
        # Validar largo mínimo
        if len(rut_limpio) < 2:
            return False

        # Separar número y DV
        numero = rut_limpio[:-1]
        dv_ingresado = rut_limpio[-1]

        # Validar que el número contenga solo dígitos
        if not numero.isdigit():
            return False

        # Calcular DV esperado y comparar
        dv_calculado = self.calcular_dv(numero)
        return dv_ingresado == dv_calculado

    def _actualizar_cache(self, rut: str, es_valido: bool):
        """Actualiza el cache con límite de tamaño."""
        if len(self._cache) >= self._max_cache_size:
            # Eliminar el primer elemento (FIFO)
            self._cache.pop(next(iter(self._cache)))

        self._cache[rut] = es_valido

    def extraer_info(self, rut: str) -> Optional[dict]:
        """
        Extrae información detallada del RUT.

        Args:
            rut: RUT a analizar

        Returns:
            Diccionario con información o None si es inválido
        """
        if not self.validar(rut):
            return None

        rut_limpio = self.limpiar(rut)
        numero = int(rut_limpio[:-1])

        return {
            'numero': numero,
            'dv': rut_limpio[-1],
            'formateado': self.formatear(rut_limpio),
            'sin_formato': rut_limpio,
            'es_empresa': numero >= 50000000,  # RUTs de empresas generalmente
            'es_persona': numero < 50000000
        }


# Instancia global para usar
validator = RutValidator()
