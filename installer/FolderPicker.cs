using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

internal static class FolderPicker
{
    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Length < 1)
            return 2;

        IFileOpenDialog dialog = (IFileOpenDialog)new FileOpenDialog();
        try
        {
            FOS options;
            dialog.GetOptions(out options);
            dialog.SetOptions(options | FOS.PICKFOLDERS | FOS.FORCEFILESYSTEM | FOS.PATHMUSTEXIST);
            dialog.SetTitle("Выберите папку установки BonusDesk");
            dialog.SetOkButtonLabel("Выбрать папку");

            if (args.Length > 1 && Directory.Exists(args[1]))
            {
                Guid shellItemId = typeof(IShellItem).GUID;
                IShellItem initial;
                if (SHCreateItemFromParsingName(args[1], IntPtr.Zero, ref shellItemId, out initial) == 0)
                    dialog.SetFolder(initial);
            }

            if (dialog.Show(IntPtr.Zero) != 0)
                return 1;

            IShellItem result;
            dialog.GetResult(out result);
            IntPtr rawPath;
            result.GetDisplayName(SIGDN.FILESYSPATH, out rawPath);
            try
            {
                string selectedPath = Marshal.PtrToStringUni(rawPath) ?? string.Empty;
                if (selectedPath.Length == 0)
                    return 1;
                File.WriteAllText(args[0], selectedPath, new UTF8Encoding(false));
                return 0;
            }
            finally
            {
                Marshal.FreeCoTaskMem(rawPath);
            }
        }
        finally
        {
            Marshal.FinalReleaseComObject(dialog);
        }
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = true)]
    private static extern int SHCreateItemFromParsingName(
        string path, IntPtr bindContext, ref Guid shellItemId, out IShellItem shellItem);

    [ComImport]
    [Guid("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")]
    private class FileOpenDialog { }

    [ComImport]
    [Guid("42F85136-DB7E-439C-85F1-E4075D135FC8")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IFileDialog
    {
        [PreserveSig] int Show(IntPtr parent);
        void SetFileTypes(uint count, IntPtr filterSpec);
        void SetFileTypeIndex(uint index);
        void GetFileTypeIndex(out uint index);
        void Advise(IntPtr events, out uint cookie);
        void Unadvise(uint cookie);
        void SetOptions(FOS options);
        void GetOptions(out FOS options);
        void SetDefaultFolder(IShellItem folder);
        void SetFolder(IShellItem folder);
        void GetFolder(out IShellItem folder);
        void GetCurrentSelection(out IShellItem item);
        void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string name);
        void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string name);
        void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string title);
        void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string text);
        void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string label);
        void GetResult(out IShellItem item);
        void AddPlace(IShellItem item, int alignment);
        void SetDefaultExtension([MarshalAs(UnmanagedType.LPWStr)] string extension);
        void Close(int result);
        void SetClientGuid(ref Guid guid);
        void ClearClientData();
        void SetFilter(IntPtr filter);
    }

    [ComImport]
    [Guid("D57C7288-D4AD-4768-BE02-9D969532D960")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IFileOpenDialog : IFileDialog
    {
        [PreserveSig] new int Show(IntPtr parent);
        new void SetFileTypes(uint count, IntPtr filterSpec);
        new void SetFileTypeIndex(uint index);
        new void GetFileTypeIndex(out uint index);
        new void Advise(IntPtr events, out uint cookie);
        new void Unadvise(uint cookie);
        new void SetOptions(FOS options);
        new void GetOptions(out FOS options);
        new void SetDefaultFolder(IShellItem folder);
        new void SetFolder(IShellItem folder);
        new void GetFolder(out IShellItem folder);
        new void GetCurrentSelection(out IShellItem item);
        new void SetFileName(string name);
        new void GetFileName(out string name);
        new void SetTitle(string title);
        new void SetOkButtonLabel(string text);
        new void SetFileNameLabel(string label);
        new void GetResult(out IShellItem item);
        new void AddPlace(IShellItem item, int alignment);
        new void SetDefaultExtension(string extension);
        new void Close(int result);
        new void SetClientGuid(ref Guid guid);
        new void ClearClientData();
        new void SetFilter(IntPtr filter);
        void GetResults(out IntPtr items);
        void GetSelectedItems(out IntPtr items);
    }

    [ComImport]
    [Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IShellItem
    {
        void BindToHandler(IntPtr bindContext, ref Guid handlerId, ref Guid interfaceId, out IntPtr result);
        void GetParent(out IShellItem parent);
        void GetDisplayName(SIGDN displayName, out IntPtr name);
        void GetAttributes(uint mask, out uint attributes);
        void Compare(IShellItem other, uint hint, out int order);
    }

    [Flags]
    private enum FOS : uint
    {
        PICKFOLDERS = 0x00000020,
        FORCEFILESYSTEM = 0x00000040,
        PATHMUSTEXIST = 0x00000800
    }

    private enum SIGDN : uint
    {
        FILESYSPATH = 0x80058000
    }
}
