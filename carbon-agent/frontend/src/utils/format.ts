/**
 * Formatea un número en notación española: coma decimal, nunca punto.
 * El punto se lee como separador de millares en español (p.ej. "27.000"
 * parece "veintisiete mil"), así que nunca se debe usar toFixed() directo
 * en texto visible al usuario.
 */
export function formatEs(value: number, decimals = 2): string {
  return value.toFixed(decimals).replace('.', ',')
}
