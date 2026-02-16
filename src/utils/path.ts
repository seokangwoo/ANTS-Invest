/**
 * Utility to get the correct path including the base path if deployed in a subdirectory.
 * This is crucial for GitHub Pages deployment.
 */
export const getPath = (path: string): string => {
    // Remove leading slash if present to avoid double slashes when joining
    const cleanPath = path.startsWith('/') ? path.slice(1) : path;
    const basePath = process.env.BASE_PATH || '';

    // If basePath is present, ensure we don't double add it if the input path already includes it
    // (though the caller should generally pass relative paths)
    if (basePath && path.startsWith(basePath)) {
        return path;
    }

    return `${basePath}/${cleanPath}`;
};
