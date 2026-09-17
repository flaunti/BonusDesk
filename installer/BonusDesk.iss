#ifndef MyAppVersion
  #define MyAppVersion "2.2.1"
#endif

#define MyAppName "BonusDesk"
#define MyAppPublisher "Flaunti"
#define MyAppURL "https://github.com/flaunti/BonusDesk"
#define MyAppExeName "BonusDesk.exe"

[Setup]
AppId={{64E8E820-5CD4-41BE-A62D-F96ACF667834}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases/latest
AppComments=Проверка отчётов и подготовка списков премий
AppCopyright=© 2026 Edward Saint
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
DisableReadyPage=no
AlwaysShowDirOnReadyPage=yes
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=BonusDesk-Setup-x64
SetupIconFile=..\assets\bonusdesk.ico
WizardImageFile=assets\wizard-large.bmp
WizardSmallImageFile=assets\wizard-small.bmp
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
VersionInfoCompany=Flaunti
VersionInfoDescription=BonusDesk Setup
VersionInfoProductName=BonusDesk
VersionInfoProductVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные значки:"; Flags: unchecked

[Files]
Source: "..\dist\BonusDesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "FolderPicker.exe"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure ChooseInstallFolder(Sender: TObject);
var
  ResultCode: Integer;
  ResultFile: String;
  SelectedFolder: AnsiString;
  Parameters: String;
begin
  ExtractTemporaryFile('FolderPicker.exe');
  ResultFile := ExpandConstant('{tmp}\bonusdesk-selected-folder.txt');
  DeleteFile(ResultFile);
  Parameters := '"' + ResultFile + '" "' + WizardDirValue + '"';

  if Exec(
    ExpandConstant('{tmp}\FolderPicker.exe'),
    Parameters,
    '',
    SW_SHOWNORMAL,
    ewWaitUntilTerminated,
    ResultCode
  ) and (ResultCode = 0) and LoadStringFromFile(ResultFile, SelectedFolder) then
    WizardForm.DirEdit.Text := Trim(SelectedFolder);
end;

procedure InitializeWizard;
begin
  WizardForm.DirBrowseButton.OnClick := @ChooseInstallFolder;
  WizardForm.DirBrowseButton.Caption := 'Выбрать…';
  WizardForm.WelcomeLabel1.Caption := 'Добро пожаловать в BonusDesk';
  WizardForm.WelcomeLabel2.Caption :=
    'Установщик подготовит BonusDesk для работы на этом компьютере.' + #13#10 + #13#10 +
    'Приложение работает локально, не требует сервера и хранит данные только на вашем устройстве.';
end;
