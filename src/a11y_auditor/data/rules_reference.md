---
type: reference
related-skill: a11y-static-audit
tags: [reference, wcag, abnt, rules]
---

# `/a11y-static-audit` — REFERENCE

Catálogo completo das regras de análise estática suportadas pela skill, organizadas por nível WCAG 2.2 / ABNT NBR 17060.

---

## Mapeamento WCAG ↔ ABNT NBR 17060

| WCAG 2.2 | ABNT NBR 17060 |
|----------|-----------------|
| 1.1.1 Non-text Content | 7.2.1, 7.2.3 |
| 1.3.1 Info and Relationships | 7.4, 7.5 |
| 1.3.5 Identify Input Purpose | 7.4 |
| 1.4.4 Resize Text | 7.9 |
| 2.3.3 Animation from Interactions | 7.4 |
| 2.4.3 Focus Order | 7.5.1, 7.5.2, 7.5.4 |
| 2.4.6 Headings and Labels | 7.5 |
| 2.5.3 Label in Name | 7.2.1 |
| 2.5.8 Target Size (Minimum) | 7.6.1 |
| 3.3.1 Error Identification | 7.7 |
| 3.3.2 Labels or Instructions | 7.4 |
| 3.3.5 Help | 7.8 |
| 4.1.2 Name, Role, Value | 7.2.2, 7.2.4 |
| 4.1.3 Status Messages | 7.7 |

---

## Cumulatividade dos níveis

| `--level` | Regras aplicadas |
|-----------|-------------------|
| `A`   | apenas A |
| `AA`  | A + AA |
| `AAA` | A + AA + AAA |

---

## Convenções

### Estrutura do Finding

```ts
type Finding = {
  ruleId: string;
  level: 'A' | 'AA' | 'AAA';
  severity: 'error' | 'warning' | 'info';
  file: string;
  line: number;
  column: number;
  message: string;       // pt-BR
  fix?: string;          // sugestão de correção, pt-BR
  wcag: string[];
  abnt?: string[];
  snippet: string;
};
```

### Severidades

| Severidade | Conta p/ coverage? | Símbolo |
|------------|---------------------|---------|
| `error`    | Sim — bloqueia cobertura | ❌ |
| `warning`  | Não — mas aparece no relatório | ⚠️ |
| `info`     | Não — sugestão | ℹ️ |

---

# Regras — Nível A (obrigatórias)

## `a11y/missing-label-on-touchable`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 1.1.1, 4.1.2 |
| ABNT NBR 17060 | 7.2.1 |
| Aplica em | `Pressable`, `TouchableOpacity`, `TouchableHighlight`, `TouchableWithoutFeedback`, `TouchableNativeFeedback` |

### Descrição

Touchable com `onPress` mas **sem** `accessibilityLabel` e **sem** texto filho derivável. O leitor de tela anuncia apenas "botão" sem dizer o que ele faz.

### Pré-requisitos para disparar

- Tem `onPress` (ou está dentro de allowlist do DS).
- Não está em allowlist do DS Tangerina (ex: `TgrButtonPrimary` já injeta label).
- Não há `accessibilityLabel`.
- Filhos não contêm `<Text>` ou string literal (que serviriam como label implícito).

### Errado

```tsx
<Pressable onPress={handleSelect}>
  <Icon name="map-pin" />
</Pressable>
```

### Certo

```tsx
<Pressable onPress={handleSelect} accessibilityLabel={t('Common.A11y.SelectAddress')}>
  <Icon name="map-pin" />
</Pressable>
```

### Fix sugerido

`Adicione accessibilityLabel descrevendo a ação do botão.`

---

## `a11y/missing-role-on-button-like`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 4.1.2 |
| ABNT NBR 17060 | 7.2.2 |
| Aplica em | `Pressable`, `TouchableOpacity`, `TouchableHighlight` |

### Descrição

Touchable com `onPress` mas sem `accessibilityRole` definido. Sem o role, o leitor de tela não anuncia "botão", apenas o label — quebra o modelo mental do usuário.

### Exceção (allowlist)

Componentes do DS Tangerina que já injetam role internamente (ver tabela "Allowlist" abaixo).

### Errado

```tsx
<Pressable onPress={onLogin} accessibilityLabel="Acessar conta">
  <Text>Acessar conta</Text>
</Pressable>
```

### Certo

```tsx
<Pressable onPress={onLogin} accessibilityRole="button" accessibilityLabel="Acessar conta">
  <Text>Acessar conta</Text>
</Pressable>
```

### Fix

`Adicione accessibilityRole="button".`

---

## `a11y/image-without-alt`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 1.1.1 |
| ABNT NBR 17060 | 7.2.3 |
| Aplica em | `Image`, `Animated.Image`, `FastImage`, `SvgXml` |

### Descrição

Imagem sem indicação clara de propósito: nem `accessibilityLabel` (caso informativo) nem decoração explícita (`accessibilityElementsHidden={true}` + `importantForAccessibility="no-hide-descendants"`).

### Errado

```tsx
<Animated.Image source={bg} style={styles.bg} />
```

### Certo (decorativa)

```tsx
<Animated.Image
  source={bg}
  style={styles.bg}
  accessibilityElementsHidden
  importantForAccessibility="no-hide-descendants"
/>
```

### Certo (informativa)

```tsx
<Image source={logo} accessibilityLabel={t('Common.A11y.GolLogo')} />
```

---

## `a11y/no-text-in-button`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 1.1.1, 2.5.3 |
| ABNT NBR 17060 | 7.2.1 |
| Aplica em | Touchables com filhos apenas `<Icon>` / `<Image>` |

### Descrição

Variante específica de `a11y/missing-label-on-touchable` para casos onde o botão não tem nenhum texto visível — apenas ícone. Reportada separadamente para destacar que a UX exige um label explícito.

### Errado

```tsx
<Pressable onPress={onMenu}>
  <Icon name="menu" />
</Pressable>
```

### Certo

```tsx
<Pressable onPress={onMenu} accessibilityRole="button" accessibilityLabel={t('Common.A11y.OpenMenu')}>
  <Icon name="menu" />
</Pressable>
```

---

## `a11y/hardcoded-label-string`

| | |
|--|--|
| Severidade default | `error` (string não existe em i18n) ou `info` (string existe como valor em i18n) |
| WCAG | — (boa prática) |
| ABNT NBR 17060 | 7.3 |
| Aplica em | `accessibilityLabel`, `accessibilityHint` |

### Descrição

Prop de a11y recebe string literal em vez de `t('chave.i18n')`. Quebra a internacionalização do app.

### Lógica de severidade (i18n cross-check)

1. Carregar `pt-BR.json`, `en.json`, `es.json` (paths via `config.i18nPaths`).
2. Achatar todos os valores em um `Set<string>`.
3. Se a string literal **existe** como valor → `info` (sugestão de usar a chave).
4. Se **não existe** → `error` (string nunca foi traduzida).

### Errado

```tsx
<Pressable accessibilityLabel="Acessar conta" onPress={...} />
```

### Certo

```tsx
<Pressable accessibilityLabel={t('Login.A11y.AccessAccount')} onPress={...} />
```

---

## `a11y/form-input-without-label`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 1.3.1, 3.3.2 |
| ABNT NBR 17060 | 7.4 |
| Aplica em | `TextInput`, `TgrInputText` (quando não tem `label` prop), `TgrInputPassword` |

### Descrição

Campo de entrada sem `accessibilityLabel` e sem `label`/`placeholder` traduzido próximo. Usuário cego não sabe o que digitar.

### Errado

```tsx
<TextInput value={cpf} onChangeText={setCpf} />
```

### Certo

```tsx
<TextInput
  value={cpf}
  onChangeText={setCpf}
  accessibilityLabel={t('Login.A11y.CpfField')}
  placeholder={t('Login.Placeholder.Cpf')}
/>
```

---

## `a11y/heading-without-role`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 1.3.1, 2.4.6 |
| ABNT NBR 17060 | 7.5 |
| Aplica em | `TgrHeading`, `Text` com estilo de cabeçalho (`fontSize >= 20 && fontWeight: 'bold'`) |

### Descrição

Cabeçalho visual sem `accessibilityRole="header"`. Quebra a navegação por headings do leitor de tela (rotor iOS / nav mode Android).

### Errado

```tsx
<TgrHeading>{t('Login.Title')}</TgrHeading>
```

### Certo

```tsx
<TgrHeading accessibilityProps={{accessibilityRole: 'header'}}>
  {t('Login.Title')}
</TgrHeading>
```

---

# Regras — Nível AA (recomendadas)

## `a11y/touch-target-too-small`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 2.5.8 |
| ABNT NBR 17060 | 7.6.1 |
| Aplica em | Touchables com style declarado |

### Descrição

Touchable com `width` ou `height` declarados em style menores que o mínimo recomendado (44pt iOS / 48dp Android), e sem `hitSlop` para expansão da área de toque.

### Inferência de tamanho

1. Procurar `StyleSheet.create({...})` no arquivo e match por nome de estilo passado em `style={styles.x}`.
2. Procurar styles inline `style={{width: N, height: N}}`.
3. Quando style vem de tema dinâmico (`styled-components`, `useTheme()`): emitir como `warning` em vez de `error`, com mensagem indicando que não foi possível inferir tamanho.

### Errado

```tsx
const styles = StyleSheet.create({
  iconButton: {width: 32, height: 32},
});
<Pressable style={styles.iconButton} onPress={...} />
```

### Certo

```tsx
<Pressable style={styles.iconButton} onPress={...} hitSlop={{top: 6, bottom: 6, left: 6, right: 6}} />
```

ou aumentar o style para ≥ 44x44.

---

## `a11y/missing-accessibility-state`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 4.1.2 |
| ABNT NBR 17060 | 7.2.4 |

### Descrição

Componente com prop `disabled={true}` (ou variável) mas sem `accessibilityState={{disabled: true}}`, ou vice-versa.

### Caso especial

Combinada com `a11y/disabled-button-via-pressable-prop`: quando `Pressable` recebe `disabled={true}` literal, **rebaixar** para a outra regra (que é mais específica).

### Errado

```tsx
<TgrButtonPrimary disabled={true} onPress={onConfirm} />
```

### Certo

```tsx
<TgrButtonPrimary
  disabled={true}
  accessibilityState={{disabled: true}}
  onPress={onConfirm}
/>
```

(ou aplicar o padrão `View wrapper + pointerEvents="none"` se for evitar o trait nativo — ver `a11y/disabled-button-via-pressable-prop`.)

---

## `a11y/missing-selected-state`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 4.1.2 |
| ABNT NBR 17060 | 7.2.4 |
| Aplica em | Listas, Tabs, RadioGroups |

### Descrição

Item de lista/tab que tem estado de seleção mas não comunica via `accessibilityState={{selected: true}}`.

### Errado

```tsx
{items.map(item => (
  <Pressable key={item.id} onPress={() => select(item.id)}>
    <Text style={item.id === selectedId && styles.active}>{item.name}</Text>
  </Pressable>
))}
```

### Certo

```tsx
{items.map(item => (
  <Pressable
    key={item.id}
    onPress={() => select(item.id)}
    accessibilityRole="button"
    accessibilityState={{selected: item.id === selectedId}}
  >
    <Text style={item.id === selectedId && styles.active}>{item.name}</Text>
  </Pressable>
))}
```

---

## `a11y/focus-order-conflict`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 2.4.3, 4.1.2 |
| ABNT NBR 17060 | 7.5.2 |

### Descrição

Uso de `accessibilityElementsHidden` (iOS) sem o par `importantForAccessibility="no-hide-descendants"` (Android) ou vice-versa. Resultado: comportamento divergente entre plataformas.

### Errado

```tsx
<View accessibilityElementsHidden={true}>
  <Image source={bg} />
</View>
```

(Esconde no iOS, mas Android continua lendo.)

### Certo

```tsx
<View
  accessibilityElementsHidden={true}
  importantForAccessibility="no-hide-descendants"
>
  <Image source={bg} />
</View>
```

---

## `a11y/modal-without-view-is-modal`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 2.4.3 |
| ABNT NBR 17060 | 7.5.3 |

### Descrição

`<Modal>` (ou Drawer customizado renderizado como Modal) sem `accessibilityViewIsModal={true}` no container. O leitor de tela continua acessando elementos por trás do modal.

### Errado

```tsx
<Modal visible={isOpen} animationType="fade">
  <View style={styles.drawer}>...</View>
</Modal>
```

### Certo

```tsx
<Modal visible={isOpen} animationType="fade">
  <View style={styles.drawer} accessibilityViewIsModal={true}>...</View>
</Modal>
```

---

## `a11y/announce-on-error-missing`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 3.3.1, 4.1.3 |
| ABNT NBR 17060 | 7.7 |

### Descrição

Componente que renderiza mensagem de erro condicional, sem usar `accessibilityLiveRegion="polite"` (Android) ou `AccessibilityInfo.announceForAccessibility` (iOS).

### Errado

```tsx
{error && <Text style={styles.error}>{error}</Text>}
```

### Certo

```tsx
{error && (
  <Text
    style={styles.error}
    accessibilityLiveRegion="polite"
    accessibilityRole="alert"
  >
    {error}
  </Text>
)}
```

E no iOS:

```tsx
useEffect(() => {
  if (error) AccessibilityInfo.announceForAccessibility(error);
}, [error]);
```

---

## `a11y/heading-hierarchy-skipped`

| | |
|--|--|
| Severidade default | `warning` |
| WCAG | 2.4.6 |
| ABNT NBR 17060 | 7.5 |

### Descrição

Múltiplos `accessibilityRole="header"` na mesma tela sem distinção visual de nível. Limitação da API RN (não tem `accessibilityLevel` como na web). Reportado como warning para revisão humana.

---

## `a11y/disabled-button-via-pressable-prop`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 4.1.2 |
| ABNT NBR 17060 | 7.2.4 |

### Descrição

`Pressable` (ou Touchable) com `disabled={true}` literal — sem o pattern de wrapper externo. Gera anúncio nativo "atenuado"/"escurecido" do leitor de tela, mesmo se `accessibilityState` for sobrescrito via spread.

### Origem da regra

Lesson learned do CDACE-727 (TASK-018): override de `accessibilityState.disabled` em JS **não** suprime o trait nativo do `Pressable.disabled`.

### Errado

```tsx
<TgrButtonPrimary disabled={isDisabled} onPress={onConfirm} />
```

### Certo

```tsx
<View
  style={{opacity: isDisabled ? 0.4 : 1}}
  pointerEvents={isDisabled ? 'none' : 'auto'}
>
  <TgrButtonPrimary
    disabled={false}
    onPress={isDisabled ? () => {} : onConfirm}
    accessibilityLabel={isDisabled ? `${label}, desativado` : label}
  />
</View>
```

---

# Regras — Nível AAA (ideais)

## `a11y/missing-hint-on-complex-action`

| | |
|--|--|
| Severidade default | `warning` |
| WCAG | 3.3.5 |
| ABNT NBR 17060 | 7.8 |

### Descrição

Ações complexas (`onLongPress`, ações destrutivas como "Excluir", "Cancelar reserva") sem `accessibilityHint` explicando o resultado.

### Errado

```tsx
<TgrButtonPrimary onLongPress={onDelete} accessibilityLabel="Excluir" />
```

### Certo

```tsx
<TgrButtonPrimary
  onLongPress={onDelete}
  accessibilityLabel="Excluir"
  accessibilityHint="Toque duplo e segure para excluir a reserva permanentemente."
/>
```

---

## `a11y/animation-without-reduce-motion`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 2.3.3 |
| ABNT NBR 17060 | 7.4 |

### Descrição

`Animated.View entering={FadeIn}` (Reanimated) ou `Animated.timing` rodando sem checar `useReduceMotion()`. Viola a configuração de OS "Reduzir movimento" do usuário.

### Errado

```tsx
<Animated.View entering={FadeIn}>
  {children}
</Animated.View>
```

### Certo

```tsx
const reduceMotion = useReduceMotion();
<Animated.View entering={reduceMotion ? undefined : FadeIn}>
  {children}
</Animated.View>
```

---

## `a11y/no-live-region-on-status`

| | |
|--|--|
| Severidade default | `error` |
| WCAG | 4.1.3 |
| ABNT NBR 17060 | 7.7 |

### Descrição

Componente de status (Toast, Banner, Snackbar) sem `accessibilityLiveRegion`. Usuário de leitor de tela perde a mensagem.

---

## `a11y/missing-screen-entry-focus`

| | |
|--|--|
| Severidade default | `warning` |
| WCAG | 2.4.3 |
| ABNT NBR 17060 | 7.5.1 |
| Aplica em | Apenas em arquivos `entryFile` de tela |

### Descrição

Tela (entry file) sem `useFocusEffect` que mova o foco para o primeiro heading na entrada. Usuário de leitor de tela não sabe que mudou de tela.

### Errado

```tsx
export default function LoginScreen() {
  return <View>...</View>;
}
```

### Certo

```tsx
export default function LoginScreen() {
  const {ref: headingRef, setFocus} = useAccessibilityFocus();
  useFocusEffect(useCallback(() => { setFocus(); }, [setFocus]));
  return (
    <View>
      <View ref={headingRef} accessible>
        <TgrHeading accessibilityProps={{accessibilityRole: 'header'}}>
          {title}
        </TgrHeading>
      </View>
      ...
    </View>
  );
}
```

---

## `a11y/drawer-without-focus-restoration`

| | |
|--|--|
| Severidade default | `warning` |
| WCAG | 2.4.3 |
| ABNT NBR 17060 | 7.5.4 |

### Descrição

Drawer/Modal aberto sem callback que devolve foco ao trigger no fechamento.

---

## `a11y/missing-dynamic-type-support`

| | |
|--|--|
| Severidade default | `info` |
| WCAG | 1.4.4 |
| ABNT NBR 17060 | 7.9 |

### Descrição

Estilo `fontSize` em texto com `allowFontScaling={false}` indevido. Quebra Dynamic Type / FontSize do OS.

### Errado

```tsx
<Text style={{fontSize: 14}} allowFontScaling={false}>{label}</Text>
```

### Certo

```tsx
<Text style={{fontSize: 14}}>{label}</Text>
```

---

# Allowlist do Design System Tangerina

Componentes do `@gol-smiles/tangerina-react-native-core` que já injetam props de acessibilidade internamente. Quando importados deste módulo, certas regras **não disparam**.

| Componente | Injeta | Não dispara |
|------------|--------|-------------|
| `TgrButtonPrimary` | `accessibilityRole="button"` | `missing-role-on-button-like` |
| `TgrButtonSecondary` | `accessibilityRole="button"` | `missing-role-on-button-like` |
| `TgrButtonMini` | `accessibilityRole="button"` | `missing-role-on-button-like` |
| `TgrButtonGroup` | `accessibilityRole="button"` (nos filhos) | `missing-role-on-button-like` |
| `TgrLanguageSelector` | `accessibilityRole="button"` + label dinâmico | `missing-role-on-button-like`, `missing-label-on-touchable` |
| `TgrHeading` | (sem role automático — auditar manualmente) | — |
| `TgrParagraph` | `accessibilityRole="text"` | — |
| `TgrInputText` | label associado via prop `label` | `form-input-without-label` (se `label` prop existir) |
| `TgrInputPassword` | mesma coisa | `form-input-without-label` (se `label` prop existir) |

> A lista cresce conforme falsos positivos forem identificados na Part 5 (Validation). Cada adição deve ser registrada como lesson learned no job.

---

# Notas de implementação

## Indexação por tag JSX

Para performance, pré-indexar regras por tag de elemento JSX:

```
ruleIndex = {
  Pressable: [missing-label-on-touchable, missing-role-on-button-like, focus-order-conflict, disabled-button-via-pressable-prop, touch-target-too-small],
  Image: [image-without-alt],
  Animated_Image: [image-without-alt],
  Modal: [modal-without-view-is-modal],
  TextInput: [form-input-without-label],
  TgrHeading: [heading-without-role],
  Animated_View: [animation-without-reduce-motion],
  ...
}
```

Em cada elemento visitado no AST, rodar apenas as regras indexadas para aquela tag. Reduz drasticamente o tempo de execução em arquivos grandes.

## Cache de AST

Cada arquivo é parseado uma vez, mesmo que apareça em múltiplas telas (componente compartilhado).

## Skip de arquivos sem JSX

Se o AST não tem `JSXElement`, pular regras de JSX (utils, types, constants, helpers de string).
