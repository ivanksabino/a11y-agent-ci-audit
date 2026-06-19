---
job: agente-auditor-a11y
tags: [a11y, examples, few-shot, knowledge, react-native, wcag]
date: 2026-06-17
---

# Documentação por exemplo — Antes → Depois de A11Y validada

> Knowledge de referência do [[_Overview|Agente Auditor A11Y]]. Cada par mostra o código **antes** (com violação), o **depois** (acessível e validado) e a regra/WCAG associada. O agente usa estes exemplos como few-shot para classificar findings no diff e sugerir o `fix`.
>
> Convenção: cada exemplo cita `rule_id`, `severity`, `WCAG` e `ABNT NBR 17060`.
>
> Há dois tipos de exemplo aqui:
> - **Exemplos reais do GOL** (Parte A): trechos de arquivos versionados, extraídos de PRs de a11y já mergeados e validados — o formato de referência preferido.
> - **Exemplos sintéticos por regra** (Parte B): ilustrações mínimas de cada `rule_id`, úteis quando não há caso real equivalente.

---

# Parte A — Exemplos reais do GOL (arquivo + PR)

> Antes = `HEAD` anterior à atuação de a11y; Depois = código mergeado e validado. Caminhos relativos à raiz de `GOL_APP_Mobile`.

## A1. `HomeBaseScreen` — botões de ícone sem label + WebView oculta

- **Arquivo**: `modernization/modules/Home/screens/HomeBaseScreen/HomeBaseScreen.tsx`
- **PR**: 252636 · **Ticket**: CDACE-629 — [Acessibilidade] Correções de acessibilidade
- **Regras**: `a11y/missing-label-on-touchable`, `a11y/missing-hint-on-complex-action`, esconder elemento decorativo/invisível do leitor.

### A1.1 — `TgrButtonIcon` sem label/hint (`HeaderIsLogged`)

Os botões de ícone (`language`, `more-vertical`) não tinham texto nem label → o TalkBack/VoiceOver anunciava só "botão". O DS Tangerina **não** injeta label automático em `TgrButtonIcon` (é só ícone), então precisa de `accessibilityLabel` explícito.

```tsx
// ❌ ANTES — modernization/modules/Home/screens/HomeBaseScreen/HomeBaseScreen.tsx
<GolBox flexDirection="row" alignItems="center" gap="s1x">
  <TgrButtonIcon
    icon="language"
    onPress={navigateToPreferencesScreen}
  />

  <TgrButtonIcon
    icon="more-vertical"
    onPress={debouncedLoginPressLogged}
  />
</GolBox>
```

```tsx
// ✅ DEPOIS — labels e hints via i18n (translate)
<GolBox flexDirection="row" alignItems="center" gap="s1x">
  <TgrButtonIcon
    icon="language"
    onPress={navigateToPreferencesScreen}
    accessibilityLabel={translate(
      'Home.HomeBaseScreen.A11y.Preferences',
    )}
    accessibilityHint={translate(
      'Home.HomeBaseScreen.A11y.PreferencesHint',
    )}
  />

  <TgrButtonIcon
    icon="more-vertical"
    onPress={debouncedLoginPressLogged}
    accessibilityLabel={translate(
      'Home.HomeBaseScreen.A11y.MyAccount',
    )}
    accessibilityHint={translate(
      'Home.HomeBaseScreen.A11y.MyAccountHint',
    )}
  />
</GolBox>
```

### A1.2 — WebView invisível exposta ao leitor

A `WebView` de logout (`0×0`, fora da tela) era focável pelo leitor — virava "elemento fantasma" na navegação. Fix: removê-la da árvore de acessibilidade.

```tsx
// ❌ ANTES
{isInvisibleLogoutWebViewOpened && (
  <WebView
    style={{width: 0, height: 0}}
    source={{uri: Config.WEBVIEW_SMILES_LOGOUT}}
    onLoadEnd={() => {
      setIsInvisibleLogoutWebViewOpened(false);
    }}
  />
)}
```

```tsx
// ✅ DEPOIS
{isInvisibleLogoutWebViewOpened && (
  <WebView
    style={{width: 0, height: 0}}
    source={{uri: Config.WEBVIEW_SMILES_LOGOUT}}
    onLoadEnd={() => {
      setIsInvisibleLogoutWebViewOpened(false);
    }}
    accessible={false}
    importantForAccessibility="no"
  />
)}
```

> **Lição extraída**: `TgrButtonIcon` exige `accessibilityLabel` explícito (não tem texto filho). Elementos invisíveis/decorativos (WebView 0×0, ilustrações) saem da árvore com `accessible={false}` + `importantForAccessibility="no"` (Android) — alinhado ao padrão GOL de esconder do leitor.

> _Como adicionar mais casos reais_: `git log -i --grep="acess\|a11y" -- <arquivo>` no `GOL_APP_Mobile`, depois `git show <sha>^:<arquivo>` (antes) e `git show <sha>:<arquivo>` (depois).

---

# Parte B — Exemplos sintéticos por regra

## 1. Touchable sem label — `a11y/missing-label-on-touchable`
`severity: error` · WCAG 1.1.1, 4.1.2 · ABNT 7.2.1

O leitor anuncia só "botão", sem dizer a ação.

```tsx
// ❌ ANTES
<Pressable onPress={handleSelectAddress}>
  <Icon name="map-pin" />
</Pressable>
```

```tsx
// ✅ DEPOIS
<Pressable
  onPress={handleSelectAddress}
  accessibilityRole="button"
  accessibilityLabel={t('Common.A11y.SelectAddress')}
>
  <Icon name="map-pin" />
</Pressable>
```

---

## 2. Elemento clicável sem role — `a11y/missing-role-on-button-like`
`severity: error` · WCAG 4.1.2 · ABNT 7.2.2

`View`/`Pressable` com `onPress` precisa de `accessibilityRole` para o leitor anunciar como botão. (Componentes do DS Tangerina já injetam — não disparam.)

```tsx
// ❌ ANTES
<TouchableOpacity onPress={onConfirm}>
  <Text>Confirmar</Text>
</TouchableOpacity>
```

```tsx
// ✅ DEPOIS
<TouchableOpacity onPress={onConfirm} accessibilityRole="button">
  <Text>Confirmar</Text>
</TouchableOpacity>
```

---

## 3. Imagem informativa sem alt — `a11y/image-without-alt`
`severity: error` · WCAG 1.1.1 · ABNT 7.2.1, 7.2.3

Imagem que carrega informação precisa de label; imagem decorativa deve ser **escondida** do leitor.

```tsx
// ❌ ANTES
<Image source={require('./boarding-pass.png')} />
```

```tsx
// ✅ DEPOIS — informativa
<Image
  source={require('./boarding-pass.png')}
  accessible
  accessibilityRole="image"
  accessibilityLabel={t('Checkin.A11y.BoardingPass')}
/>

// ✅ DEPOIS — decorativa (esconde do leitor)
<Image source={require('./divider.png')} accessible={false} aria-hidden />
```

> Padrão GOL: para esconder do leitor, usar `accessible={false}` **e** `aria-hidden` juntos.

---

## 4. Label hardcoded — `a11y/hardcoded-label-string`
`severity: error` (ou `info` se a string já existe no i18n) · WCAG 1.1.1 · ABNT 7.2.1

```tsx
// ❌ ANTES
<Pressable accessibilityLabel="Voltar para a tela anterior" onPress={goBack}>
```

```tsx
// ✅ DEPOIS
<Pressable accessibilityLabel={t('Common.A11y.GoBack')} onPress={goBack}>
```

---

## 5. Input de formulário sem label — `a11y/form-input-without-label`
`severity: error` · WCAG 1.3.1, 3.3.2 · ABNT 7.4

```tsx
// ❌ ANTES
<TextInput value={cpf} onChangeText={setCpf} placeholder="CPF" />
```

```tsx
// ✅ DEPOIS
<TextInput
  value={cpf}
  onChangeText={setCpf}
  placeholder={t('Login.CpfPlaceholder')}
  accessibilityLabel={t('Login.A11y.CpfField')}
  accessibilityHint={t('Login.A11y.CpfHint')}
  keyboardType="numeric"
/>
```

> `placeholder` **não** é label — some quando o usuário digita. O leitor precisa de `accessibilityLabel`.

---

## 6. Título sem role de header — `a11y/heading-without-role`
`severity: warning` · WCAG 1.3.1, 2.4.6 · ABNT 7.5

```tsx
// ❌ ANTES
<Text style={styles.title}>Selecione seu voo</Text>
```

```tsx
// ✅ DEPOIS
<Text style={styles.title} accessibilityRole="header">
  {t('FlightList.Title')}
</Text>
```

---

## 7. Estado de seleção não exposto — `a11y/missing-selected-state`
`severity: error` · WCAG 4.1.2 · ABNT 7.2.4

```tsx
// ❌ ANTES
<Pressable onPress={() => setSelected(id)} style={isSelected && styles.active}>
  <Text>{seatNumber}</Text>
</Pressable>
```

```tsx
// ✅ DEPOIS
<Pressable
  onPress={() => setSelected(id)}
  accessibilityRole="button"
  accessibilityState={{ selected: isSelected }}
  style={isSelected && styles.active}
>
  <Text>{seatNumber}</Text>
</Pressable>
```

---

## 8. Botão desabilitado só visual — `a11y/missing-accessibility-state` / `disabled-button-via-pressable-prop`
`severity: error` · WCAG 4.1.2 · ABNT 7.2.4

```tsx
// ❌ ANTES — leitor anuncia como botão ativo
<Pressable disabled={!isValid} onPress={submit} style={!isValid && styles.muted}>
  <Text>Continuar</Text>
</Pressable>
```

```tsx
// ✅ DEPOIS
<Pressable
  disabled={!isValid}
  onPress={submit}
  accessibilityRole="button"
  accessibilityState={{ disabled: !isValid }}
  style={!isValid && styles.muted}
>
  <Text>Continuar</Text>
</Pressable>
```

---

## 9. Modal sem marcação modal — `a11y/modal-without-view-is-modal`
`severity: error` · WCAG 2.4.3, 4.1.2 · ABNT 7.5.1

```tsx
// ❌ ANTES — foco do leitor "vaza" para o conteúdo atrás
<Modal visible={open}>
  <BottomSheetContent />
</Modal>
```

```tsx
// ✅ DEPOIS
<Modal visible={open}>
  <View accessibilityViewIsModal importantForAccessibility="yes">
    <BottomSheetContent />
  </View>
</Modal>
```

---

## 10. Erro de validação não anunciado — `a11y/announce-on-error-missing` / `no-live-region-on-status`
`severity: error` · WCAG 4.1.3, 3.3.1 · ABNT 7.7

```tsx
// ❌ ANTES — erro aparece visualmente, leitor não fala
{hasError && <Text style={styles.error}>CPF inválido</Text>}
```

```tsx
// ✅ DEPOIS
{hasError && (
  <Text
    style={styles.error}
    accessibilityLiveRegion="polite"
    accessibilityRole="alert"
  >
    {t('Login.A11y.InvalidCpf')}
  </Text>
)}
```

---

## 11. Alvo de toque pequeno — `a11y/touch-target-too-small`
`severity: warning` · WCAG 2.5.8 · ABNT 7.6.1

Alvo mínimo recomendado: 44×44 pt (iOS) / 48×48 dp (Android).

```tsx
// ❌ ANTES
<Pressable onPress={onClose} style={{ width: 24, height: 24 }}>
  <Icon name="close" />
</Pressable>
```

```tsx
// ✅ DEPOIS
<Pressable
  onPress={onClose}
  accessibilityRole="button"
  accessibilityLabel={t('Common.A11y.Close')}
  hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
  style={{ width: 24, height: 24 }}
>
  <Icon name="close" />
</Pressable>
```

---

## 12. Ação complexa sem hint — `a11y/missing-hint-on-complex-action`
`severity: warning` · WCAG 3.3.2 · ABNT 7.4, 7.8

```tsx
// ❌ ANTES
<Pressable accessibilityRole="button" accessibilityLabel="Trocar voo" onPress={swap} />
```

```tsx
// ✅ DEPOIS
<Pressable
  accessibilityRole="button"
  accessibilityLabel={t('Flight.A11y.SwapLabel')}
  accessibilityHint={t('Flight.A11y.SwapHint')} // "Abre a busca para escolher outro voo"
  onPress={swap}
/>
```

---

## 13. Foco de entrada da tela — `a11y/missing-screen-entry-focus`
`severity: warning` · WCAG 2.4.3 · ABNT 7.5.2

```tsx
// ✅ DEPOIS — mover o foco do leitor para o título ao abrir a tela
const titleRef = useRef(null);
useEffect(() => {
  const node = findNodeHandle(titleRef.current);
  if (node) AccessibilityInfo.setAccessibilityFocus(node);
}, []);

<Text ref={titleRef} accessibilityRole="header">{t('Mfa.Title')}</Text>
```

---

## Tabela-resumo (severidade → gate)

| Regra | Severity | Bloqueia gate? |
|-------|----------|----------------|
| missing-label-on-touchable | error | ✅ |
| missing-role-on-button-like | error | ✅ |
| image-without-alt | error | ✅ |
| hardcoded-label-string | error / info | ✅ se error |
| form-input-without-label | error | ✅ |
| missing-selected-state | error | ✅ |
| missing-accessibility-state | error | ✅ |
| modal-without-view-is-modal | error | ✅ |
| announce-on-error-missing | error | ✅ |
| heading-without-role | warning | ❌ |
| touch-target-too-small | warning | ❌ |
| missing-hint-on-complex-action | warning | ❌ |
| missing-screen-entry-focus | warning | ❌ |

> Calibração inicial sugerida: **só `error` bloqueia**. `warning`/`info` viram comentário no PR sem reprovar. Endurecer depois conforme o time amadurece.
