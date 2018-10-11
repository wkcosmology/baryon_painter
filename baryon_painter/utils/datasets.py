import os
import collections

import numpy as np

class BAHAMASDataset:
    """Dataset that deals with loading the BAHAMAS stacks.
    
    Arguments
    ---------
    files :list
        List of dicts describing the data files. See below for a description of 
        the required entries.
    root_path :str, optional
        Path where the data files will be looked for. If not provided, the data 
        files are expected to be in the current directory or specified with 
        absolute paths. (default None).
    redshifts : list, numpy.ndarray, optional
        Redshifts that should be included. If not provided, uses all redshifts 
        in the files. (default None).
    input_field : str, optional
        Field to be used as input (default ``"dm"``).
    label_fields : list, optional
        List of fields to be used as labels. If not provided uses all fields in 
        the files (except input_field). (default None).
    n_tile : int, optional
        Number of tiles per stack, where the total number of tiles is n_tile^2. 
        (default 4).
    transform : callable, optional
        Transform to be applied to the samples. The callable needs to have the 
        signature ``f(x, field, z, **kwargs)``, where ``x`` is the data to be 
        transformed, ``field`` the field of the data, and ``z`` the redshift. 
        (default ``lambda x, field, z, **kwargs: x``).
    inverse_transform : callable, optional
        Inverse transform. The required signature is the same as for the 
        transform. 
        (default ``lambda x, field, z, **kwargs: (field, z, kwargs["mean"], kwargs["var"])``).
    verbose : bool, optional
        Verbosity of the output (default False).
    """
    def __init__(self, files, root_path=None,
                 redshifts=[],
                 input_field="dm", label_fields=[], 
                 n_tile=4,
                 L=400,
                 transform=lambda x, field, z, **kwargs: x, 
                 inverse_transform=lambda x, field, z, **kwargs: (field, z, kwargs["mean"], kwargs["var"]),
                 n_feature_per_field=1,
                 verbose=False):
        self.data = {}
        
        self.fields = set()
        self.redshifts = set()
        
        # Check which fields and redshifts are available
        for f in files:
            if isinstance(f, dict):
                self.fields.add(f["field"])
                self.redshifts.add(f["z"])
            else:
                raise ValueError("files entry is not a dict.")
        
        if label_fields != []:
            # Select the intersection of the available fields and requested fields.
            if self.fields.issuperset([input_field] + label_fields):
                self.fields = self.fields.intersection([input_field] + label_fields)
            else:
                missing = set([input_field] + label_fields) - self.fields
                raise ValueError(f"The requested fields are not in the file list: field(s) {missing} is missing.")
        
        self.input_field = input_field
        self.label_fields = list(self.fields - set([self.input_field]))
        
        if redshifts != []:
            # Select the intersection of the available redshifts and requested redshifts.
            if self.redshifts.issuperset(redshifts):
                self.redshifts = self.redshifts.intersection(redshifts)
            else:
                missing = set(redshifts) - self.redshifts
                raise ValueError(f"The requested redshifts are not in the file list: redshift(s) {missing} is missing.")

        self.redshifts = np.array(sorted(list(self.redshifts)))
              
        # Load the files now
        for f in files:
            field = f["field"]
            z = f["z"]
            if field not in self.fields or z not in self.redshifts:
                # Don't load fields that are not requested
                continue
                
            if field not in self.data:
                self.data[field] = {}
            if z not in self.data[field]:
                self.data[field][z] = {}
                    
            fn100 = f["file_100"]
            fn150 = f["file_150"]
            if root_path is not None:
                fn100 = os.path.join(root_path, fn100)
                fn150 = os.path.join(root_path, fn150)

            self.data[field][z]["100"] = np.load(fn100, mmap_mode="r")
            self.data[field][z]["150"] = np.load(fn150, mmap_mode="r")

            self.data[field][z]["mean_100"] = f["mean_100"]
            self.data[field][z]["mean_150"] = f["mean_150"]
            self.data[field][z]["var_100"] = f["var_100"]
            self.data[field][z]["var_150"] = f["var_150"]

            self.n_stack_100, self.n_grid, _ = self.data[field][z]["100"].shape
            self.n_stack_150, _, _ = self.data[field][z]["150"].shape
        
        self.n_tile = n_tile
        self.tile_size = self.n_grid//self.n_tile
        self.n_sample = (self.n_stack_100*self.n_tile**2)*(self.n_stack_150*self.n_tile**2)

        self.L = L
        self.tile_L = self.L/self.n_tile
                                
        self.transform = transform
        self.inverse_transform = inverse_transform

        self.n_feature_per_field = n_feature_per_field
        
    def create_transform(self, field, z, **stats):
        """Creates a callable for the transform of the form f(x)."""

        return lambda x: self.transform(x, field, z, **stats)
    
    def create_inverse_transform(self, field, z, **stats):
        """Creates a callable for the inverse transform of the form f(x)."""

        return lambda x: self.inverse_transform(x, field, z, **stats)
        
    def get_transforms(self, idx=None, z=None):
        """Get the transforms for a stack.

        Arguments
        ---------
        idx : int, optional
            Index of the stack.
        z : float, optional
            Redshift of the stack.
            
        Either ``idx`` or ``z`` have to be specified.
        
        Returns
        -------
        transforms : list
            List of the transforms for the input and label fields.
        """
        if idx is None and z is None:
            raise ValueError("Either idx or z have to be specified.")
            
        if z is None:
            z = self.sample_idx_to_redshift(idx)

        transforms = []
        for field in [self.input_field]+self.label_fields:
            stats = self.get_stack_stats(field, z)
            transforms.append(self.create_transform(field, z, **stats))

        return transforms
    
    def get_inverse_transforms(self, idx=None, z=None):
        """Get the inverse transforms for a stack.

        Arguments
        ---------
        idx : int, optional
            Index of the stack.
        z : float, optional
            Redshift of the stack.
            
        Either ``idx`` or ``z`` have to be specified.
            

        Returns
        -------
        inv_transforms : list
            List of the inverse transforms for the input and label fields.
        """
        if idx is None and z is None:
            raise ValueError("Either idx or z have to be specified.")
            
        if z is None:
            z = self.sample_idx_to_redshift(idx)

        inv_transforms = []
        for field in [self.input_field]+self.label_fields:
            stats = self.get_stack_stats(field, z)
            inv_transforms.append(self.create_inverse_transform(field, z, **stats))

        return inv_transforms

    def get_stack_stats(self, field, z):
        """Returns stack stats for a given field and redshift.
        
        Arguments
        ---------
        field : str
            Field of the requested stack.
        z : float
            Redshift of the requested stack.
            
        Returns
        -------
        stats : dict
            Dictionary with statistics of the stack. At this point only contains 
            the mean and variance of all stacks in the dataset.
        """
        mean_100 = self.data[field][z]["mean_100"]
        mean_150 = self.data[field][z]["mean_150"]
        var_100 = self.data[field][z]["var_100"]
        var_150 = self.data[field][z]["var_150"]
        
        stats = {"mean" : mean_100+mean_150,
                 "var"  : var_100+var_150}
        return stats

    def get_stack(self, field, z, flat_idx):
        """Returns a stack for a given field, redshift, and index.
        
        Arguments
        ---------
        field : str
            Field of the requested stack.
        z : float
            Redshift of the requested stack.
        flat_idx : int
            Index of the requested stack.
            
        Returns
        -------
        stack : 2d numpy.array
            250 Mpc/h equivalent stack.
        stats : dict
            Dictionary with statistics of the stack. At this point only contains 
            the mean and variance of all stacks in the dataset.
        """

        flat_idx = flat_idx%self.n_sample
        
        idx = np.unravel_index(flat_idx, dims=(self.n_stack_100, self.n_tile, self.n_tile, 
                                               self.n_stack_150, self.n_tile, self.n_tile))
        
        slice_idx_100 = idx[0]
        slice_idx_150 = idx[3]
        tile_idx_100 = slice(idx[1]*self.tile_size, (idx[1]+1)*self.tile_size), slice(idx[2]*self.tile_size, (idx[2]+1)*self.tile_size)
        tile_idx_150 = slice(idx[4]*self.tile_size, (idx[4]+1)*self.tile_size), slice(idx[5]*self.tile_size, (idx[5]+1)*self.tile_size)
        d_100 = self.data[field][z]["100"][slice_idx_100][tile_idx_100]
        d_150 = self.data[field][z]["150"][slice_idx_150][tile_idx_150]
        
        stats = self.get_stack_stats(field, z)
        
        return d_100+d_150, stats
    
    def sample_idx_to_redshift(self, idx):
        """Converts an index into the corresponding redshift."""

        redshift_idx = idx//self.n_sample
        z = self.redshifts[redshift_idx]
        return z
    
    def get_input_sample(self, idx, transform=True):
        """Get a sample for the input field.

        Arguments
        ---------
        idx : int
            The index of the sample.
        transform :bool, optional
            Transform the data. If True, returns the  inverse transform. 
            (default True). 
        
        Returns
        -------
        output : 2d numpy.array
            Stack for the input field and index ``idx``.
        """

        z = self.sample_idx_to_redshift(idx)

        d_input, input_stats = self.get_stack(self.input_field, z, idx)
        if transform:
            d_input = self.transform(d_input, self.input_field, z, **input_stats)

        return d_input

    def get_label_sample(self, idx, transform=True):
        """Get a sample for the label fields.

        Arguments
        ---------
        idx : int
            The index of the sample.
        transform : bool, optional
            Transform the data. If True, returns the inverse transform. 
            (default True). 
        
        Returns
        -------
        output : list
            List of stacks for the input field and index ``idx``.
        """

        z = self.sample_idx_to_redshift(idx)
        
        d_labels = []
        for label_field in self.label_fields:
            d, stats = self.get_stack(label_field, z, idx)
            if transform:
                d = self.transform(d, label_field, z, **stats)
            
            d_labels.append(d)
            
        return d_labels
    
    def __len__(self):
        """Return total number of samples.

        The total number of samples is given by 
        ``(n_stack_100*n_tile**2)*(n_stack_150*n_tile**2)*len(redshifts)``.
        """
        return self.n_sample*len(self.redshifts)
    
    def __getitem__(self, idx):
        """Get a sample.

        Arguments
        ---------
        idx : int
            Index of the sample.

        Returns
        -------
        output : list
            List of sample fields, with order ``input_field, label_fields``.
        idx : int
            Index of the requested sample. This can be used to access the
            inverse transforms.
        """
        if not isinstance(idx, collections.Iterable):
            d_input = self.get_input_sample(idx)
            d_label = self.get_label_sample(idx)
            
            return [d_input]+d_label, idx
        else:
            raise NotImplementedError("Only int indicies are supported for now.")

